# OpenWebUI YT Video Transcription via Whisper ASR Webserver
This is an improved version of my old function [WhisperWebUI Video Transcription](https://openwebui.com/f/mindphuq/whisperwebui_video_transcription) function. This one uses [Whisper ASR Webserver](https://github.com/ahmetoner/whisper-asr-webservice) instead for the transcription. There is a `yt-dlp` dependency requirement now.

Function for Open WebUI, which retrieves text and video meta from a provided YouTube URL by calling your local Whisper ASR Webserver endpoint, then sends it back to the LLM.

Utilizes [Whisper ASR Webserver](https://github.com/ahmetoner/whisper-asr-webservice) to get the youtube video transcription.

### How it looks
![image](https://github.com/user-attachments/assets/dc89a6f3-c068-4a59-bd97-5f8cc09996d5)

### CHANGELOG
#### 1.0.0
- works the same as [WhisperWebUI Video Transcription](https://openwebui.com/f/mindphuq/whisperwebui_video_transcription)
- added UserValve to bypass the cache when enabled

Add it to your OpenWebUI instance - [https://openwebui.com/f/mindphuq/whisper_asr_video_transcription](https://openwebui.com/f/mindphuq/whisper_asr_video_transcription)

Old implementation is moved to the [whisper-webui](https://github.com/karamanliev/open-webui-yt-whisper/tree/whisper-webui) branch. It can be added to your OpenWebUI instance from [https://openwebui.com/f/mindphuq/whisperwebui_video_transcription](https://openwebui.com/f/mindphuq/whisperwebui_video_transcription)
