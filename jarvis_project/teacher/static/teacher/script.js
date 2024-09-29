let mediaRecorder;
let audioChunks = [];
let statusElement = document.getElementById('status');
const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

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
            console.log("Selected MIME type: ${type}");
            return type;
        }
    }
    console.warn('No supported MIME type found for MediaRecorder.');
    return '';
}

// Function to initialize MediaRecorder
function initMediaRecorder(stream) {
    // Log stream details
    console.log('Initializing MediaRecorder with stream:', stream);

    const audioTracks = stream.getAudioTracks();
    
    console.log("Audio Tracks: ${audioTracks.length}");

    if (audioTracks.length === 0) {
        console.error('No audio tracks found in the MediaStream.');
        alert('Nenhum dispositivo de áudio encontrado.');
        return;
    }

    const mimeType = getSupportedMimeType();

    if (!mimeType) {
        alert('Seu navegador não suporta os tipos de mídia necessários para gravação.');
        // Optionally, disable recording buttons
        document.getElementById('startBtn').disabled = true;
        document.getElementById('stopBtn').disabled = true;
        return;
    }

    try {
        mediaRecorder = new MediaRecorder(stream, { mimeType: mimeType });
        console.log("MediaRecorder initialized with MIME type: ${mimeType}");
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

// Request media devices (audio only)
navigator.mediaDevices.getUserMedia({ audio: true })
    .then(function(stream) {
        console.log('MediaStream obtained:', stream);
        // Removed videoElement.srcObject as we're not handling video

        // Initialize MediaRecorder
        initMediaRecorder(stream);
    })
    .catch(function(err) {
        console.error('Error accessing media devices:', err);
        if (err.name === 'NotAllowedError') {
            alert('Permissões de áudio foram negadas.');
        } else {
            alert('Erro ao acessar dispositivos de mídia: ' + err.message);
        }
    });

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
        console.error('Failed to start MediaRecorder:', e);
        alert('Erro ao iniciar a gravação.');
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