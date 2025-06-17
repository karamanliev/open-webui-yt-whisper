# OpenWebUI YT Video Transcription via Whisper-WebUI
Function for Open WebUI, which retrieves text and video meta from a provided YouTube URL by calling the Whisper-WebUI endpoint, then sends it back to the LLM.

Utilizes [Whisper-WebUI](https://github.com/jhj0517/Whisper-WebUI) to get the youtube video transcription.

### How it looks
![image](https://github.com/user-attachments/assets/dc89a6f3-c068-4a59-bd97-5f8cc09996d5)

### CHANGELOG
#### 1.3.0
- Added caching of transcriptions
- Updated the formatting of the message that is sent to the LLM
- Misc improvements

#### 1.2.0
- move some settings to uservalves
- add translate to english setting
- send the channel name to the LLM

Add it to your OpenWebUI instance - [https://openwebui.com/f/mindphuq/openrouter_stats_and_cost_tracking](https://openwebui.com/f/mindphuq/whisperwebui_video_transcription)
