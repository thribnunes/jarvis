from django.shortcuts import render


import base64
from io import BytesIO
from PIL import Image
from django.http import JsonResponse
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from openai import OpenAI
from gtts import gTTS
import os
import tempfile
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import time
import httpx

def index(request):
    return render(request, 'index.html')  # Ensure 'index.html' is in teacher/templates/

@csrf_exempt
def process_input(request):
    api_key = settings.OPENAI_API_KEY
    if request.method == 'POST':
        # Retrieve audio and image data from the POST request
        audio_file = request.FILES.get('audio')
        image_data = request.POST.get('image')  # This may be None if not sent

        # Check if the audio file was provided
        if not audio_file:
            return JsonResponse({'error': 'Nenhum áudio foi fornecido.'}, status=400)

        # Initialize variable to hold decoded image bytes
        image_bytes = None

        # Decode the image if image data is provided
        if image_data:
            try:
                # Split the base64 string to remove the header and decode the image data
                image_data = image_data.split(',')[1]  # Assumes "data:image/jpeg;base64," format
                image_bytes = base64.b64decode(image_data)
                print("Imagem recebida e decodificada com sucesso.")
            except Exception as e:
                print(f"Erro ao decodificar a imagem: {e}")
                return JsonResponse({'error': 'Erro ao processar a imagem fornecida.'}, status=400)

        # Save the uploaded audio file to a temporary file
        try:
            temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix='.webm')
            for chunk in audio_file.chunks():
                temp_audio_file.write(chunk)
            temp_audio_file.close()
            print("Áudio salvo com sucesso.")
        except Exception as e:
            print(f"Erro ao salvar o áudio: {e}")
            return JsonResponse({'error': 'Erro ao processar o áudio.'}, status=500)

        # Initialize transcription variables
        transcription = ''
        attempts = 0
        max_attempts = 3  # Maximum number of retry attempts

        # Use OpenAI to transcribe the audio with retry logic
        client = OpenAI(api_key=api_key)
        while attempts < max_attempts:
            try:
                with open(temp_audio_file.name, 'rb') as audio_file_for_transcription:
                    transcription_response = client.audio.transcriptions.create(
                        model='whisper-1',
                        file=audio_file_for_transcription,
                        language='pt'
                    )
                    transcription = transcription_response.text
                    print(f"Transcrição do áudio: {transcription}")
                break  # Exit the loop if transcription is successful
            except Exception as e:
                attempts += 1
                print(f"Erro na tentativa {attempts} de transcrição. Exception: {str(e)}")
                time.sleep(5)  # Wait for 5 seconds before retrying
        else:
            # If all attempts fail, clean up and return an error
            print("Falha ao transcrever após 3 tentativas.")
            os.unlink(temp_audio_file.name)  # Delete the temporary audio file
            return JsonResponse({'error': 'Erro ao transcrever o áudio.'}, status=500)

        # Delete the temporary audio file after transcription
        os.unlink(temp_audio_file.name)

        # Check if transcription was successful
        if not transcription:
            return JsonResponse({'error': 'Não foi possível transcrever o áudio.'}, status=500)

        # Format the question using Langchain
        try:
            langchain_client = ChatOpenAI(model='gpt-4o-mini', temperature=0.7)

            # Prepare the question with image (if provided) and transcription using Langchain's HumanMessage format
            inputs = [
                HumanMessage(
                    content=[
                        {
                            "type": "text",
                            "text": f"""
                                Você é um professor extremamente qualificado e respeitado.
                                Você sempre fala em português brasileiro.
                                Nunca utilize símbolos ou equações; descreva todos os elementos, símbolos e operações matemáticas por extenso e em português brasileiro, utilizando palavras.
                                Incentive o usuário a refletir sobre cada etapa do processo, fazendo perguntas para garantir a compreensão e guiá-lo de forma interativa.
                                Se o usuário estiver no caminho certo, elogie e continue oferecendo orientações para que ele avance na solução.
                                Explique como abordar e resolver o problema, passo a passo, sem entregar a solução final.
                                Dê respostas curtas e objetivas, sempre buscando orientar o usuário.
                                
                                Conversa atual:
                                Aluno: {transcription}
                                Imagem: { "Imagem fornecida" if image_bytes else "Nenhuma imagem fornecida." }
                            """
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}" if image_bytes else None
                            }
                        }
                    ]
                )
            ]
            print(inputs)

            # Obtain response from ChatGPT through Langchain
            response = langchain_client.stream(inputs)
            answer = ''
            for resp in response:
                answer += resp.content
            print(f"Resposta do ChatGPT: {answer}")

        except Exception as e:
            print(f"Erro ao obter resposta do ChatGPT com Langchain: {e}")
            return JsonResponse({'error': 'Erro ao processar a resposta do ChatGPT.'}, status=500)

        # Generate speech from the answer using gTTS
        try:
            tts = gTTS(text=answer, lang='pt')
            audio_response_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            tts.save(audio_response_file.name)
            with open(audio_response_file.name, 'rb') as f:
                audio_content = f.read()
            audio_base64 = base64.b64encode(audio_content).decode('utf-8')
            os.unlink(audio_response_file.name)
            print("Áudio de resposta gerado com sucesso.")
        except Exception as e:
            audio_base64 = ''
            print(f"Erro ao gerar áudio da resposta: {e}")

        # Return the response as JSON
        return JsonResponse({'answer': answer, 'audio_base64': audio_base64})
    else:
        return JsonResponse({'error': 'Método de solicitação inválido.'}, status=405)