from django.shortcuts import render
from django.http import JsonResponse
import os
import base64
from io import BytesIO
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
import tempfile
from gtts import gTTS
import time  # Import time for sleep in retry logic
from django.conf import settings

def index(request):
    return render(request, 'index.html')  # Ensure 'index.html' is in teacher/templates/

@csrf_exempt
def process_input(request):
    api_key = settings.OPEN_AI_KEY
    print("KEY", api_key)

    if request.method == 'POST':
        # Retrieve audio and image data from the POST request
        audio_file = request.FILES.get('audio')
        image_data = request.POST.get('image')  # This may be None if not sent

        # Initialize variable to hold decoded image bytes
        image_bytes = None

        # Decode the image if image data is provided
        if image_data:
            try:
                # Split the base64 string to remove the header
                image_data = image_data.split(',')[1]
                # Decode the base64 image data
                image_bytes = base64.b64decode(image_data)
                # Optional: Process the image using PIL or other libraries if needed
                # from PIL import Image
                # image = Image.open(BytesIO(image_bytes))
            except Exception as e:
                image_bytes = None
                print(f"Image Decoding Error: {e}")

        # Save the uploaded audio file to a temporary file
        print("OPEN AI KEY: ", api_key)
        client = OpenAI(
            api_key=api_key,  # this is also the default, it can be omitted
        )
        
        try:
            temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix='.webm')
            for chunk in audio_file.chunks():
                temp_audio_file.write(chunk)
            temp_audio_file.close()
        except Exception as e:
            print(f"Audio Saving Error: {e}")
            return JsonResponse({'error': 'Erro ao processar o áudio.'})

        # Initialize transcription variables
        transcription = ''
        attempts = 0
        max_attempts = 3  # Maximum number of retry attempts

        # Transcribe the audio with retry logic
        while attempts < max_attempts:
            try:
                with open(temp_audio_file.name, 'rb') as audio_file_for_transcription:
                    # Use the updated OpenAI transcription method
                    transcription_response = client.audio.transcriptions.create(
                        model='whisper-1',
                        file=audio_file_for_transcription,
                        language='pt'
                    )
                    print(transcription_response)
                    transcription = transcription_response.text
                break  # Exit the loop if transcription is successful
            except Exception as e:
                attempts += 1
                print(f"Attempt {attempts} failed. Exception: {str(e)}")
                time.sleep(5)  # Wait for 5 seconds before retrying
        else:
            # If all attempts fail, clean up and return an error
            print("Failed to transcribe after 3 attempts.")
            os.unlink(temp_audio_file.name)  # Delete the temporary audio file
            return JsonResponse({'error': 'Erro ao transcrever o áudio.'})

        # Delete the temporary audio file after transcription
        os.unlink(temp_audio_file.name)

        # Check if transcription was successful
        if not transcription:
            return JsonResponse({'error': 'Não foi possível transcrever o áudio.'})

        # Prepare the prompt for ChatGPT
        prompt = f"""
Você é um professor extremamente qualificado e respeitado.
Você sempre fala em português brasileiro.
Nunca utilize símbolos ou equações; descreva todos os elementos, símbolos e operações matemáticas por extenso e em português brasileiro, utilizando palavras.
Incentive o usuário a refletir sobre cada etapa do processo, fazendo perguntas para garantir a compreensão e guiá-lo de forma interativa.
Se o usuário estiver no caminho certo, elogie e continue oferecendo orientações para que ele avance na solução.
Explique como abordar e resolver o problema, passo a passo, sem entregar a solução final.
Dê respostas curtas e objetivas, sempre buscando orientar o usuário.

Aluno: {transcription}
Imagem: {"(descrição da imagem se necessário)" if image_bytes else "Nenhuma imagem fornecida."}
"""

        # Get response from ChatGPT
        try:
            response = client.chat.completions.create(
                model='gpt-4',
                messages=[{'role': 'system', 'content': prompt}],
                temperature=0.7,
            )
            print(response)
            answer = response.choices[0].message.content
        except Exception as e:
            answer = "Desculpe, ocorreu um erro ao processar sua pergunta."
            print(f"ChatGPT Error: {e}")

        # Generate speech from the answer using gTTS
        try:
            tts = gTTS(text=answer, lang='pt')
            audio_response_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            tts.save(audio_response_file.name)
            with open(audio_response_file.name, 'rb') as f:
                audio_content = f.read()
            audio_base64 = base64.b64encode(audio_content).decode('utf-8')
            os.unlink(audio_response_file.name)
        except Exception as e:
            audio_base64 = ''
            print(f"TTS Error: {e}")

        # Return the response as JSON
        return JsonResponse({'answer': answer, 'audio_base64': audio_base64})
    else:
        return JsonResponse({'error': 'Método de solicitação inválido.'})