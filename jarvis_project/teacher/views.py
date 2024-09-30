from django.shortcuts import render
import base64
from django.http import JsonResponse
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from openai import OpenAI
import os
import io
import tempfile
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import time

def index(request):
    return render(request, 'index.html')

@csrf_exempt
def process_input(request):
    api_key = settings.OPENAI_API_KEY
    client = OpenAI(api_key=api_key)
    if request.method == 'POST':
        # Retrieve audio and image data from the POST request
        audio_file = request.FILES.get('audio')
        image_data = request.POST.get('image')

        # Check if the audio file was provided
        if not audio_file:
            return JsonResponse({'error': 'Nenhum áudio foi fornecido.'}, status=400)

        # Initialize variable to hold decoded image bytes
        image_bytes = None

        # Decode the image if image data is provided
        if image_data:
            try:
                # Split the base64 string to remove the header and decode the image data
                image_data = image_data.split(',')[1]
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
        max_attempts = 3

        # Use OpenAI to transcribe the audio with retry logic
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
                break
            except Exception as e:
                attempts += 1
                print(f"Erro na tentativa {attempts} de transcrição. Exception: {str(e)}")
                time.sleep(5)
        else:
            print("Falha ao transcrever após 3 tentativas.")
            os.unlink(temp_audio_file.name)
            return JsonResponse({'error': 'Erro ao transcrever o áudio.'}, status=500)

        # Delete the temporary audio file after transcription
        os.unlink(temp_audio_file.name)

        # Check if transcription was successful
        if not transcription:
            return JsonResponse({'error': 'Não foi possível transcrever o áudio.'}, status=500)

        # Retrieve conversation history from the session
        conversation_history = request.session.get('conversation_history', '')
        # Append the user's message to the conversation history
        conversation_history += f"Aluno: {transcription}\n"

        # Limit conversation history to prevent exceeding model context length
        max_history_length = 2000
        if len(conversation_history) > max_history_length:
            conversation_history = conversation_history[-max_history_length:]

        # Format the question using Langchain
        try:
            langchain_client = ChatOpenAI(model='gpt-4o-mini', temperature=0.7)

            # Prepare the question with image and conversation history
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
                                {conversation_history}
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

            # Obtain response from ChatGPT through Langchain
            print(inputs)
            response = langchain_client(inputs)
            answer = response.content
            print(f"Resposta do ChatGPT: {answer}")

        except Exception as e:
            print(f"Erro ao obter resposta do ChatGPT com Langchain: {e}")
            return JsonResponse({'error': 'Erro ao processar a resposta do ChatGPT.'}, status=500)

        # Append the AI's response to the conversation history
        conversation_history += f"Professor: {answer}\n"
        # Save the updated conversation history back into the session
        request.session['conversation_history'] = conversation_history

        # Generate speech from the answer using your OpenAI TTS function
        try:
            audio_content = speak(answer, client)
            audio_base64 = base64.b64encode(audio_content).decode('utf-8')
            print("Áudio de resposta gerado com sucesso.")
        except Exception as e:
            audio_base64 = ''
            print(f"Erro ao gerar áudio da resposta: {e}")
            return JsonResponse({'error': 'Erro ao gerar áudio da resposta.'}, status=500)

        # Return the response as JSON, including transcription
        return JsonResponse({'transcription': transcription, 'answer': answer, 'audio_base64': audio_base64})
    else:
        return JsonResponse({'error': 'Método de solicitação inválido.'}, status=405)

@csrf_exempt
def reset_conversation(request):
    if request.method == 'POST':
        request.session['conversation_history'] = ''
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False})

def speak(text, client):
    try:
        # Using OpenAI API for text-to-speech
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice="onyx",
            response_format="mp3",
            speed=1.3,
            input=text
        ) as response:
            silence_threshold = 0.01
            stream_start = False
            audio_buffer = io.BytesIO()  # Buffer to store audio data

            for chunk in response.iter_bytes(chunk_size=1024):
                if stream_start:
                    audio_buffer.write(chunk)  # Write audio chunks to buffer
                else:
                    if max(chunk) > silence_threshold:
                        audio_buffer.write(chunk)
                        stream_start = True

            # Return the audio content from the buffer
            audio_buffer.seek(0)  # Move to the start of the buffer
            return audio_buffer.read()

    except Exception as e:
        print(f"Erro durante a síntese de fala: {e}")
        raise e  # Rethrow the error to be handled by the view
