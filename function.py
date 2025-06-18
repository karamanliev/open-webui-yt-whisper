"""
title: OpenWebUI YT Whisper Transcription
description: Retrieves text and video meta from a provided YouTube URL by calling the Whisper-WebUI endpoint, then sends it back to the LLM.
author: Hristo Karamanliev
author_url: https://github.com/karamanliev
version: 1.3.0
"""

import re
import json
import requests
import time
import html
import os
from pydantic import BaseModel, Field
from open_webui.utils.misc import get_last_user_message
from typing import Callable, Awaitable, Any, Optional, Literal

class EventEmitter:
    def __init__(self, event_emitter: Callable[[dict], Any] = None):
        self.event_emitter = event_emitter

    async def emit(self, description="Unknown State", status="in_progress", done=False):
        """
        Emits an event to the provided event_emitter callback.
        """
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
                                "distances": [
                                    0.014996514655649662,
                                ],
                            }
                        ]
                    },
                }
            )


class Filter:
    class Valves(BaseModel):
        WHISPER_WEBUI_URL: str = Field(
            "http://192.168.100.2:7860",
            description="Whisper WebUI url (https://github.com/jhj0517/Whisper-WebUI)",
        )
        WHISPER_MODEL: Literal[
            "tiny.en",
            "tiny",
            "base.en",
            "base",
            "small.en",
            "small",
            "medium.en",
            "medium",
            "large-v1",
            "large-v2",
            "large-v3",
            "large",
            "distil-large-v2",
            "distil-medium.en",
            "distil-small.en",
            "distil-large-v3",
            "large-v3-turbo",
            "turbo",
            "deepdml--faster-whisper-large-v3-turbo-ct2",
            "mobiuslabsgmbh--faster-whisper-large-v3-turbo",
        ] = Field(
            default="deepdml--faster-whisper-large-v3-turbo-ct2",
            description="Select whisper model to use",
        )
        CACHE_DIR: str = Field(
            default="./transcription_cache",
            description="Directory to store cached transcriptions",
        )
        pass

    class UserValves(BaseModel):
        WHISPER_LANGUAGE: Literal[
            "Automatic Detection",
            "afrikaans",
            "albanian",
            "amharic",
            "arabic",
            "armenian",
            "assamese",
            "azerbaijani",
            "bashkir",
            "basque",
            "belarusian",
            "bengali",
            "bosnian",
            "breton",
            "bulgarian",
            "cantonese",
            "catalan",
            "chinese",
            "croatian",
            "czech",
            "danish",
            "dutch",
            "english",
            "estonian",
            "faroese",
            "finnish",
            "french",
            "galician",
            "georgian",
            "german",
            "greek",
            "gujarati",
            "haitian creole",
            "hausa",
            "hawaiian",
            "hebrew",
            "hindi",
            "hungarian",
            "icelandic",
            "indonesian",
            "italian",
            "japanese",
            "javanese",
            "kannada",
            "kazakh",
            "khmer",
            "korean",
            "lao",
            "latin",
            "latvian",
            "lingala",
            "lithuanian",
            "luxembourgish",
            "macedonian",
            "malagasy",
            "malay",
            "malayalam",
            "maltese",
            "maori",
            "marathi",
            "mongolian",
            "myanmar",
            "nepali",
            "norwegian",
            "nynorsk",
            "occitan",
            "pashto",
            "persian",
            "polish",
            "portuguese",
            "punjabi",
            "romanian",
            "russian",
            "sanskrit",
            "serbian",
            "shona",
            "sindhi",
            "sinhala",
            "slovak",
            "slovenian",
            "somali",
            "spanish",
            "sundanese",
            "swahili",
            "swedish",
            "tagalog",
            "tajik",
            "tamil",
            "tatar",
            "telugu",
            "thai",
            "tibetan",
            "turkish",
            "turkmen",
            "ukrainian",
            "urdu",
            "uzbek",
            "vietnamese",
            "welsh",
            "yiddish",
            "yoruba",
        ] = Field(
            default="Automatic Detection",
            description="Select language for the transcription, or leave it to auto",
        )
        TRANSLATE_TO_ENGLISH: bool = Field(
            default=False, description="Translate the transcrition to english?"
        )
        pass

    def __init__(self):
        self.valves = self.Valves()

    def _get_cache_filename(self, video_id):
        return f"{video_id}.txt"

    async def inlet(
        self,
        body: dict,
        __event_emitter__: Callable[[Any], Awaitable[None]],
        __user__: Optional[dict] = None,
    ) -> dict:
        emitter = EventEmitter(__event_emitter__)

        user_valves = __user__.get("valves")
        if not user_valves:
            user_valves = self.UserValves()

        # print("===== INLET =====", json.dumps(body, indent=4))

        messages = body["messages"]
        user_message = get_last_user_message(messages)

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

        video_id_match = re.search(r"v=([A-Za-z0-9_-]{11})", video_url)
        if not video_id_match:
            await emitter.emit(
                status="error",
                description=f"Cannot extract video ID from URL: {video_url}",
                done=True,
            )
            return body

        # Create cache directory if it doesn't exist
        cache_dir = self.valves.CACHE_DIR
        os.makedirs(cache_dir, exist_ok=True)

        # Generate cache filename
        cache_filename = self._get_cache_filename(
            video_id
        )
        cache_filepath = os.path.join(cache_dir, cache_filename)

        # Check if cache exists
        message_to_cache = None
        if os.path.exists(cache_filepath):
            await emitter.emit(description=f"Loading cached transcription for video {video_id}")

            try:
                with open(cache_filepath, "r", encoding="utf-8") as f:
                    message_to_cache = f.read()

                # Extract the transcript from the cached combined_message
                transcript_match = re.search(r"## YouTube Video Transcript:\n(.*)", message_to_cache, re.DOTALL)
                final_text = transcript_match.group(1) if transcript_match else ""

                # Extract the video title from the cached data
                title_match = re.search(r"- Title: (.*)\n", message_to_cache)
                video_title = title_match.group(1) if title_match else "YouTube Video"

                await emitter.emit(
                    status="complete",
                    description=f"Loaded cached transcription for {video_title}",
                    done=True,
                )

                await emitter.emit_source(
                    name=video_title, link=video_url, content=final_text
                )

                combined_message = (
                    f"## Original User Message:\n"
                        f"{original_text}\n\n"
                        f"{message_to_cache}"
                ).strip()

                messages[-1]["content"] = combined_message
                body["messages"] = messages
                # print("===== CACHE HIT =====", json.dumps(body, indent=4))
                return body

            except Exception as e:
                await emitter.emit(
                    description=f"Error loading cache, proceeding with transcription: {str(e)}"
                )

        reqs = requests.get(video_url)

        pattern = re.compile(
            r"var ytInitialPlayerResponse = ({.*?});</script>", re.DOTALL
        )
        match = pattern.search(reqs.text)
        video_description = ""
        vido_channel = ""
        if match:
            player_response = json.loads(match.group(1))
            video_details = player_response.get("videoDetails", {})
            video_description = video_details.get("shortDescription", "")
            video_channel = video_details.get("author", "")

        titleRE = re.compile("<title>(.+?)</title>")
        video_title = html.unescape(titleRE.search(reqs.text).group(1))

        await emitter.emit(description=f"Transcribing {video_title}")

        base_url = self.valves.WHISPER_WEBUI_URL
        post_url = f"{base_url}/gradio_api/call/transcribe_youtube"

        try:
            SELECTED_WHISPER_MODEL = self.valves.WHISPER_MODEL
            SELECTED_LANGUAGE = user_valves.WHISPER_LANGUAGE
            SELECTED_TRANSLATE = user_valves.TRANSLATE_TO_ENGLISH

            payload = json.dumps(
                {
                    "data": [
                        video_url,
                        "txt",
                        False,
                        SELECTED_WHISPER_MODEL,
                        SELECTED_LANGUAGE,
                        SELECTED_TRANSLATE,
                        5,
                        -1,
                        0.6,
                        "float16",
                        5,
                        1,
                        True,
                        0.5,
                        "",
                        0,
                        2.4,
                        1,
                        1,
                        0,
                        "",
                        True,
                        "[-1]",
                        1,
                        False,
                        "\"'“¿([{-",
                        "\"'.。,，!！?？:：”)]}、",
                        0,
                        30,
                        0,
                        "",
                        0.5,
                        1,
                        24,
                        True,
                        False,
                        0.5,
                        250,
                        9999,
                        1000,
                        2000,
                        False,
                        "cuda",
                        "",
                        True,
                        False,
                        "UVR-MDX-NET-Inst_HQ_4",
                        "cuda",
                        256,
                        False,
                        True,
                    ],
                }
            )
            headers = {"Content-Type": "application/json"}

            response = requests.request("POST", post_url, headers=headers, data=payload)

            response.raise_for_status()
            response_data = response.json()

            if "event_id" not in response_data:
                await emitter.emit(
                    status="error",
                    description="No event_id returned in the response.",
                    done=True,
                )
                return ""

            event_id = response_data["event_id"]
            await emitter.emit(description=f"Downloading {video_title}...")

            stream_url = f"{base_url}/gradio_api/call/transcribe_youtube/{event_id}"

            stream_response = requests.get(stream_url, stream=True, timeout=300)
            stream_response.raise_for_status()

            lines = []
            total_time = time.time()
            for chunk in stream_response.iter_lines(decode_unicode=True):
                if chunk.startswith("event: heartbeat"):
                    now = time.time()
                    elapsed = round(now - total_time, 2)
                    await emitter.emit(
                        status="transcribing",
                        description=f"Transcribing {video_title} using {SELECTED_WHISPER_MODEL}.. {elapsed}s",
                        done=False,
                    )

                elif chunk.startswith("event: complete"):
                    pass

                elif chunk.startswith("data:"):
                    if "Done in" in chunk:
                        data = chunk[6:].strip()
                        data = json.loads(data)
                        text_arr = data[0].split(".")
                        del text_arr[0]
                        text = ".".join(text_arr)[2:]
                        lines.append(text)

            final_text = "\n".join(lines)

            now = time.time()
            elapsed = round(now - total_time, 2)

            await emitter.emit(
                status="complete",
                description=f"Transcribed {video_title} successfully using {SELECTED_WHISPER_MODEL} in {elapsed}s",
                done=True,
            )
            await emitter.emit_source(
                name=video_title, link=video_url, content=final_text
            )

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

            # Save to cache
            try:
                with open(cache_filepath, "w", encoding="utf-8") as f:
                    f.write(message_to_cache)
                print(f"Saved transcription to cache: {cache_filepath}")
            except Exception as e:
                print(f"Failed to save cache: {str(e)}")

            messages[-1]["content"] = combined_message
            body["messages"] = messages
            return body

        except requests.RequestException as e:
            print(e)
            await emitter.emit(
                status="error",
                description=f"Error while calling the transcription endpoint: {str(e)}",
                done=True,
            )
            return body
        except Exception as e:
            await emitter.emit(
                status="error",
                description=f"Unexpected error: {str(e)}",
                done=True,
            )
            return body

    # def outlet(self, body: dict) -> None:
        # print("===== OUTLET =====", json.dumps(body, indent=4))
