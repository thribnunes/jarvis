// teacher/static/teacher/script.js

let mediaRecorder;
let audioChunks = [];
let statusElement = document.getElementById('status');
const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
const videoElement = document.getElementById('video');
const canvasElement = document.getElementById('canvas');
const sendImageCheckbox = document.getElementById('sendImageCheckbox');

// Function to determine the best supported MIME type for audio
function getSupportedMimeType() {
    const possibleTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/ogg',
        'audio/mp4'
    ];

    for (let type of possibleTypes) {
        if (MediaRecorder.isTypeSupported(type)) {
            console.log(`Selected MIME type: ${type}`);
            return type;
        }
    }
    console.warn('No supported MIME type found for MediaRecorder.');
    return '';
}

// Function to initialize MediaRecorder
function initMediaRecorder(stream) {
    console.log('Initializing MediaRecorder with stream:', stream);

    const audioTracks = stream.getAudioTracks();
    if (audioTracks.length === 0) {
        console.error('No audio tracks found in the MediaStream.');
        alert('Nenhum dispositivo de áudio encontrado.');
        return;
    }

    const mimeType = getSupportedMimeType();
    if (!mimeType) {
        alert('Seu navegador não suporta os tipos de mídia necessários para gravação.');
        document.getElementById('startBtn').disabled = true;
        document.getElementById('stopBtn').disabled = true;
        return;
    }

    // **Create an audio-only stream**
    const audioStream = new MediaStream(audioTracks);

    try {
        mediaRecorder = new MediaRecorder(audioStream, { mimeType: mimeType });
        console.log(`MediaRecorder initialized with MIME type: ${mimeType}`);
    } catch (e) {
        console.error('Failed to initialize MediaRecorder:', e);
        alert('Erro ao iniciar o gravador de mídia.');
        return;
    }

    mediaRecorder.ondataavailable = function(e) {
        if (e.data && e.data.size > 0) {
            audioChunks.push(e.data);
            console.log('Data available:', e.data);
        }
    };

    mediaRecorder.onerror = function(e) {
        console.error('MediaRecorder error:', e.error);
        alert('Erro ao gravar mídia: ' + e.error.message);
    };
}

// Request media devices (audio and video)
navigator.mediaDevices.getUserMedia({ video: true, audio: true })
    .then(function(stream) {
        console.log('MediaStream obtained:', stream);
        videoElement.srcObject = stream;
        initMediaRecorder(stream);
    })
    .catch(function(err) {
        console.error('Error accessing media devices:', err);
        if (err.name === 'NotAllowedError') {
            alert('Permissões de áudio/câmera foram negadas.');
        } else {
            alert('Erro ao acessar dispositivos de mídia: ' + err.message);
        }
    });

// Capture an image from the video stream
function captureImage() {
    const context = canvasElement.getContext('2d');
    context.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);
    return canvasElement.toDataURL('image/jpeg'); // Return the image in Base64 format
}

// Start Recording
document.getElementById('startBtn').onclick = function() {
    if (!mediaRecorder) {
        alert('MediaRecorder não está disponível.');
        return;
    }

    if (mediaRecorder.state === 'recording') {
        alert('Gravação já está em andamento.');
        return;
    }

    audioChunks = [];
    try {
        mediaRecorder.start();
        console.log('MediaRecorder started:', mediaRecorder.state);
        statusElement.innerText = 'Gravação iniciada...';
    } catch (e) {
        if (e.name === 'NotSupportedError') {
            alert('Erro ao iniciar a gravação: O tipo MIME ou o fluxo de mídia não são suportados.');
        } else {
            alert('Erro ao iniciar a gravação: ' + e.message);
        }
        console.error('Failed to start MediaRecorder:', e);
    }
};

// Stop Recording and Send Data
document.getElementById('stopBtn').onclick = function() {
    if (!mediaRecorder) {
        alert('MediaRecorder não está disponível.');
        return;
    }

    if (mediaRecorder.state !== 'recording') {
        alert('MediaRecorder não está gravando.');
        return;
    }

    try {
        mediaRecorder.stop();
        console.log('MediaRecorder stopped:', mediaRecorder.state);
        statusElement.innerText = 'Gravação parada. Processando...';
    } catch (e) {
        console.error('Failed to stop MediaRecorder:', e);
        alert('Erro ao parar a gravação.');
    }

    mediaRecorder.onstop = function() {
        let audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
        let formData = new FormData();
        formData.append('audio', audioBlob, 'audio.webm');
        console.log('Audio blob created:', audioBlob);

        // Capture image if the checkbox is checked
        if (sendImageCheckbox.checked) {
            const imageData = captureImage();
            formData.append('image', imageData); // Add the image data to the form
            console.log('Image data appended to FormData');
        }

        fetch('/process_input/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken
            },
        })
        .then(response => response.json())
        .then(data => {
            statusElement.innerText = '';
            if (data.error) {
                alert(data.error);
                return;
            }
            document.getElementById('answer').innerText = data.answer;
            if (data.audio_base64) {
                let audioElement = document.getElementById('responseAudio');
                audioElement.src = 'data:audio/mp3;base64,' + data.audio_base64;
                audioElement.play();
            } else {
                alert('Erro ao gerar áudio da resposta.');
            }
        })
        .catch(error => {
            statusElement.innerText = '';
            console.error('Fetch error:', error);
            alert('Erro ao processar solicitação: ' + error.message);
        });
    };
};
