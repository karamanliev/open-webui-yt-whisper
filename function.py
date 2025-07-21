"""
title: OpenWebUI YT Whisper Transcription
description: Retrieves text and video meta from a provided YouTube URL by calling the Whisper-ASR-Webservice endpoint, then sends it back to the LLM.
author: Hristo Karamanliev
author_url: https://github.com/karamanliev
requirements: yt-dlp
version: 1.0.0
"""

import re
import json
import requests
import os
import subprocess
import tempfile
import shutil
import html
from pydantic import BaseModel, Field
from open_webui.utils.misc import get_last_user_message
from typing import Callable, Awaitable, Any, Optional, Literal

class EventEmitter:
    def __init__(self, event_emitter: Callable[[dict], Any] = None):
        self.event_emitter = event_emitter

    async def emit(self, description="Unknown State", status="in_progress", done=False):
        if self.event_emitter:
            await self.event_emitter(
                {
                    "type": "status",
                    "data": {
                        "status": status,
                        "description": description,
                        "done": done,
                    },
                }
            )

    async def emit_source(self, name="test", link="Unknown State", content="Text"):
        if self.event_emitter:
            await self.event_emitter(
                {
                    "type": "chat:completion",
                    "data": {
                        "sources": [
                            {
                                "source": {
                                    "type": "doc",
                                    "name": name,
                                    "collection_name": f"41e2d2e91c1ebaf1ece7ec9700ea1a6bb050b62b865cabfa71905a5604423dc{name}",
                                    "status": "uploaded",
                                    "url": link,
                                    "error": "",
                                    "file": {
                                        "data": {"content": content},
                                        "meta": {"name": name},
                                    },
                                },
                                "document": [content],
                                "metadata": [
                                    {
                                        "embedding_config": '{"engine": "ollama", "model": "bge-m3"}',
                                        "language": "en-US",
                                        "source": name,
                                        "start_index": 0,
                                        "title": name,
                                        "score": 0.014996514655649662,
                                    },
                                ],
                                "distances": [0.014996514655649662],
                            }
                        ]
                    },
                }
            )


class Filter:
    class Valves(BaseModel):
        ASR_URL: str = Field(
            "http://localhost:9000",
            description="ASR service URL",
        )
        CACHE_DIR: str = Field(
            default="./transcription_cache",
            description="Directory to store cached transcriptions",
        )

    class UserValves(BaseModel):
        BYPASS_CACHE: bool = Field(
            default=False,
            description="Bypass cached transcriptions and force re-transcription",
        )
        LANGUAGE: Literal[
            "Auto detect",
            "Afrikaans", "Albanian", "Amharic", "Arabic", "Armenian", "Assamese", "Azerbaijani",
            "Bashkir", "Basque", "Belarusian", "Bengali", "Bosnian", "Breton", "Bulgarian",
            "Cantonese", "Catalan", "Chinese", "Croatian", "Czech", "Danish", "Dutch", "English",
            "Estonian", "Faroese", "Finnish", "French", "Galician", "Georgian", "German", "Greek",
            "Gujarati", "Haitian", "Hausa", "Hawaiian", "Hebrew", "Hindi", "Hungarian", "Icelandic",
            "Indonesian", "Italian", "Japanese", "Javanese", "Kannada", "Kazakh", "Khmer", "Korean",
            "Lao", "Latin", "Latvian", "Lingala", "Lithuanian", "Luxembourgish", "Macedonian",
            "Malagasy", "Malay", "Malayalam", "Maltese", "Maori", "Marathi", "Mongolian", "Myanmar",
            "Nepali", "Norwegian", "Norwegian Nynorsk", "Occitan", "Pashto", "Persian", "Polish",
            "Portuguese", "Punjabi", "Romanian", "Russian", "Sanskrit", "Serbian", "Shona", "Sindhi",
            "Sinhala", "Slovak", "Slovenian", "Somali", "Spanish", "Sundanese", "Swahili", "Swedish",
            "Tagalog", "Tajik", "Tamil", "Tatar", "Telugu", "Thai", "Tibetan", "Turkish", "Turkmen",
            "Ukrainian", "Urdu", "Uzbek", "Vietnamese", "Welsh", "Yiddish", "Yoruba"
        ] = Field(
            default="Auto detect",
            description="Select language for transcription"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.LANGUAGE_MAP = {
            "Auto detect": None,
            "Afrikaans": "af", "Albanian": "sq", "Amharic": "am", "Arabic": "ar", "Armenian": "hy",
            "Assamese": "as", "Azerbaijani": "az", "Bashkir": "ba", "Basque": "eu", "Belarusian": "be",
            "Bengali": "bn", "Bosnian": "bs", "Breton": "br", "Bulgarian": "bg", "Cantonese": "yue",
            "Catalan": "ca", "Chinese": "zh", "Croatian": "hr", "Czech": "cs", "Danish": "da",
            "Dutch": "nl", "English": "en", "Estonian": "et", "Faroese": "fo", "Finnish": "fi",
            "French": "fr", "Galician": "gl", "Georgian": "ka", "German": "de", "Greek": "el",
            "Gujarati": "gu", "Haitian": "ht", "Hausa": "ha", "Hawaiian": "haw", "Hebrew": "he",
            "Hindi": "hi", "Hungarian": "hu", "Icelandic": "is", "Indonesian": "id", "Italian": "it",
            "Japanese": "ja", "Javanese": "jw", "Kannada": "kn", "Kazakh": "kk", "Khmer": "km",
            "Korean": "ko", "Lao": "lo", "Latin": "la", "Latvian": "lv", "Lingala": "ln",
            "Lithuanian": "lt", "Luxembourgish": "lb", "Macedonian": "mk", "Malagasy": "mg",
            "Malay": "ms", "Malayalam": "ml", "Maltese": "mt", "Maori": "mi", "Marathi": "mr",
            "Mongolian": "mn", "Myanmar": "my", "Nepali": "ne", "Norwegian": "no",
            "Norwegian Nynorsk": "nn", "Occitan": "oc", "Pashto": "ps", "Persian": "fa",
            "Polish": "pl", "Portuguese": "pt", "Punjabi": "pa", "Romanian": "ro", "Russian": "ru",
            "Sanskrit": "sa", "Serbian": "sr", "Shona": "sn", "Sindhi": "sd", "Sinhala": "si",
            "Slovak": "sk", "Slovenian": "sl", "Somali": "so", "Spanish": "es", "Sundanese": "su",
            "Swahili": "sw", "Swedish": "sv", "Tagalog": "tl", "Tajik": "tg", "Tamil": "ta",
            "Tatar": "tt", "Telugu": "te", "Thai": "th", "Tibetan": "bo", "Turkish": "tr",
            "Turkmen": "tk", "Ukrainian": "uk", "Urdu": "ur", "Uzbek": "uz", "Vietnamese": "vi",
            "Welsh": "cy", "Yiddish": "yi", "Yoruba": "yo"
        }

    def _get_cache_filename(self, video_id):
        return f"{video_id}.txt"

    async def inlet(
        self,
        body: dict,
        __event_emitter__: Callable[[Any], Awaitable[None]],
        __user__: Optional[dict] = None,
    ) -> dict:
        emitter = EventEmitter(__event_emitter__)
        messages = body["messages"]
        user_message = get_last_user_message(messages)

        user_valves = __user__.get("valves") if __user__ else None
        if not user_valves:
            user_valves = self.UserValves()

        youtube_match = re.search(
            r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})", user_message
        )
        if not youtube_match:
            return body

        original_text = re.sub(
            r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_-]{11}",
            "",
            user_message,
        ).strip()

        video_id = youtube_match.group(1)
        video_thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        video_url = f"https://youtube.com/watch?v={video_id}"

        cache_dir = self.valves.CACHE_DIR
        os.makedirs(cache_dir, exist_ok=True)

        cache_filename = self._get_cache_filename(video_id)
        cache_filepath = os.path.join(cache_dir, cache_filename)

        if os.path.exists(cache_filepath) and not user_valves.BYPASS_CACHE:
            await emitter.emit(description=f"Loading cached transcription for video {video_id}")

            try:
                with open(cache_filepath, "r", encoding="utf-8") as f:
                    message_to_cache = f.read()

                transcript_match = re.search(r"## YouTube Video Transcript:\n(.*)", message_to_cache, re.DOTALL)
                final_text = transcript_match.group(1) if transcript_match else ""

                title_match = re.search(r"- Title: (.*)\n", message_to_cache)
                video_title = title_match.group(1) if title_match else "YouTube Video"

                await emitter.emit(
                    status="complete",
                    description=f"Loaded cached transcription for {video_title}",
                    done=True,
                )

                await emitter.emit_source(name=video_title, link=video_url, content=final_text)

                combined_message = (
                    f"## Original User Message:\n"
                    f"{original_text}\n"
                    f"---\n\n"
                    f"{message_to_cache}"
                ).strip()

                messages[-1]["content"] = combined_message
                body["messages"] = messages
                return body

            except Exception as e:
                await emitter.emit(description=f"Error loading cache: {str(e)}")

        if user_valves.BYPASS_CACHE and os.path.exists(cache_filepath):
            os.remove(cache_filepath)
            await emitter.emit(description="Bypassing cache - will re-transcribe video")

        reqs = requests.get(video_url)

        pattern = re.compile(
            r"var ytInitialPlayerResponse = ({.*?});</script>", re.DOTALL
        )
        match = pattern.search(reqs.text)
        video_description = ""
        video_channel = ""
        if match:
            player_response = json.loads(match.group(1))
            video_details = player_response.get("videoDetails", {})
            video_description = video_details.get("shortDescription", "")
            video_channel = video_details.get("author", "")

        titleRE = re.compile("<title>(.+?)</title>")
        video_title = html.unescape(titleRE.search(reqs.text).group(1))

        await emitter.emit(description=f"Downloading audio for {video_title}")

        temp_dir = tempfile.mkdtemp()
        audio_path = None

        try:
            cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "wav",
                "--output", f"{temp_dir}/audio.%(ext)s",
                video_url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            for file in os.listdir(temp_dir):
                if file.endswith((".wav", ".mp3")):
                    audio_path = os.path.join(temp_dir, file)
                    break

            if not audio_path:
                raise Exception("No audio file found after download")

            language_code = self.LANGUAGE_MAP.get(user_valves.LANGUAGE)
            language_text = f" in {user_valves.LANGUAGE}" if language_code else ""
            await emitter.emit(description=f"Transcribing {video_title}{language_text}")

            asr_url = f"{self.valves.ASR_URL}/asr"

            with open(audio_path, "rb") as f:
                files = {"audio_file": (os.path.basename(audio_path), f, "audio/wav")}
                data = {}
                if language_code:
                    data['language'] = language_code

                response = requests.post(asr_url, files=files, data=data, timeout=300)

                if response.status_code == 500:
                    await emitter.emit(
                        status="error",
                        description=f"Server error (500): {response.text}. Check ASR service logs.",
                        done=True
                    )
                    return body

                response.raise_for_status()

            try:
                if "application/json" in response.headers.get("content-type", ""):
                    transcript_data = response.json()
                    final_text = transcript_data.get("text", "")
                else:
                    final_text = response.text.strip()

                if not final_text:
                    await emitter.emit(
                        status="error",
                        description="No transcription text returned",
                        done=True
                    )
                    return body

            except json.JSONDecodeError:
                final_text = response.text.strip()
                if not final_text:
                    await emitter.emit(
                        status="error",
                        description="Invalid response format and no text content",
                        done=True
                    )
                    return body

            await emitter.emit(
                status="complete",
                description=f"Transcribed {video_title} successfully",
                done=True,
            )

            await emitter.emit_source(name=video_title, link=video_url, content=final_text)

            message_to_cache = (
                f"## YouTube Video Details:\n"
                f"- URL: {video_url}\n"
                f"- Title: {video_title}\n"
                f"- Channel: {video_channel}\n"
                f"- Thumbnail: {video_thumbnail}\n"
                f"- Description:\n```\n{video_description}\n```\n"
                f"---\n\n"
                f"## YouTube Video Transcript:\n{final_text}"
            ).strip()

            combined_message = (
                f"## Original User Message:\n"
                f"{original_text}\n"
                f"---\n\n"
                f"{message_to_cache}"
            ).strip()

            try:
                with open(cache_filepath, "w", encoding="utf-8") as f:
                    f.write(message_to_cache)
            except Exception as e:
                print(f"Failed to save cache: {str(e)}")

            messages[-1]["content"] = combined_message
            body["messages"] = messages
            return body

        except subprocess.CalledProcessError as e:
            await emitter.emit(
                status="error",
                description=f"Error downloading audio: {e.stderr}",
                done=True,
            )
            return body
        except requests.RequestException as e:
            await emitter.emit(
                status="error",
                description=f"ASR request failed: {str(e)}",
                done=True
            )
            return body
        except Exception as e:
            await emitter.emit(
                status="error",
                description=f"Error: {str(e)}",
                done=True,
            )
            return body
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

