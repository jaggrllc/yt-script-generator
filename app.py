import streamlit as st
import io

st.set_page_config(page_title="YouTube Script Generator", page_icon="🎬", layout="wide")

st.title("🎬 YouTube Video Script Generator + Voiceover")
st.caption("Multiple input types • Start + End intro • Channel name • Privacy clear")

# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("API Keys")
    openai_key = st.text_input("OpenAI API Key", type="password")
    serpapi_key = st.text_input("SerpAPI Key (optional)", type="password")
    use_research = st.checkbox("Use SerpAPI research", value=True)
    st.divider()
    model = st.selectbox("Script Model", ["gpt-4o-mini", "gpt-4o", "gpt-4.1"], index=2)
    temperature = st.slider("Creativity", 0.0, 1.0, 0.5)
    st.divider()
    if st.button("🗑️ Clear Video Script Content from Session (Privacy)", type="secondary", use_container_width=True):
        keys_to_clear = ["generated_script", "voiceover_audio", "fact_check", "research"]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.generated_script = ""
        st.session_state.voiceover_audio = None
        st.success("Session content cleared for privacy.")
        st.rerun()

# ── Main Inputs ────────────────────────────────────────────────────
st.subheader("Input Sources")

proposed = st.text_area(
    "Proposed Video Script / Topic / Outline (optional)",
    height=150,
    placeholder="Paste a full outline, draft script, or topic description here..."
)

youtube_urls = st.text_area(
    "YouTube Video URLs (optional, one per line)",
    height=100,
    placeholder="https://www.youtube.com/watch?v=...\nhttps://youtu.be/..."
)

news_urls = st.text_area(
    "News Site URLs (optional, one per line)",
    height=100,
    placeholder="https://www.cnn.com/...\nhttps://www.bbc.com/..."
)

headlines = st.text_area(
    "Simple Headline Titles (optional, one per line)",
    height=100,
    placeholder="Learjet 60 crashes in Greenacres, Florida\nNine people killed in private jet accident"
)

col1, col2, col3 = st.columns(3)
with col1:
    tone = st.selectbox("Tone", ["Educational", "Conversational", "Storytelling", "Energetic", "Professional"])
with col2:
    length = st.selectbox("Target Length", ["3-5 min", "6-10 min", "11-15 min", "15+ min"])
with col3:
    style = st.selectbox("Style", ["Standard YouTube", "Tutorial", "Review", "Story", "Listicle"])

generate_btn = st.button("🚀 Generate & Proofread Script", type="primary", use_container_width=True)

# ── Lazy imports ───────────────────────────────────────────────────
def get_openai():
    from openai import OpenAI
    return OpenAI

def get_serpapi():
    import serpapi
    return serpapi

def get_audio_tools():
    from pydub import AudioSegment
    from pydub.effects import normalize, compress_dynamic_range
    return AudioSegment, normalize, compress_dynamic_range

# ── Functions ──────────────────────────────────────────────────────
def search_facts(query: str, api_key: str) -> str:
    if not api_key:
        return "Research disabled or no SerpAPI key."
    try:
        serpapi = get_serpapi()
        client = serpapi.Client(api_key=api_key)
        lower = query.lower()
        search_query = query
        if any(word in lower for word in ["learjet", "crash", "accident", "2026", "n722bd", "greenacres"]):
            search_query = (
                f"{query} November 2026 "
                f"-site:facebook.com -site:instagram.com -site:twitter.com -site:x.com -site:tiktok.com "
                f"(site:cnn.com OR site:bbc.com OR site:reuters.com OR site:apnews.com OR "
                f"site:wikipedia.org OR site:ntsb.gov OR site:faa.gov OR site:aviation-safety.net)"
            )
        results = client.search({"engine": "google", "q": search_query, "num": 12, "hl": "en", "gl": "us"})
        snippets = []
        for r in results.get("organic_results", [])[:10]:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            link = r.get("link", "")
            if any(d in link.lower() for d in ["facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com"]):
                continue
            if title or snippet:
                snippets.append(f"- {title}\n  {snippet}\n  Source: {link}")
        return "\n\n".join(snippets) if snippets else "No strong search results found."
    except Exception as e:
        return f"SerpAPI error: {str(e)}"

def research_is_weak(research: str) -> bool:
    weak = ["No strong search results", "SerpAPI error", "Research disabled", "no SerpAPI key"]
    return any(p in research for p in weak) or len(research.strip()) < 250

def build_user_request(proposed, youtube_urls, news_urls, headlines):
    parts = []
    if proposed.strip():
        parts.append(f"Proposed script / topic / outline:\n{proposed.strip()}")
    if youtube_urls.strip():
        parts.append(f"YouTube video URLs to reference:\n{youtube_urls.strip()}")
    if news_urls.strip():
        parts.append(f"News article URLs to reference:\n{news_urls.strip()}")
    if headlines.strip():
        parts.append(f"Headline titles to base the video on:\n{headlines.strip()}")
    return "\n\n".join(parts) if parts else "No specific input provided. Create a general script on the given topic."

def generate_script(user_request: str, research: str, openai_client) -> str:
    prompt = f"""You are a careful YouTube scriptwriter who prioritizes accuracy and clarity.

User request / source material:
{user_request}

Tone: {tone}
Target length: {length}
Style: {style}

Research (may be empty):
{research}

CRITICAL RULES:
- Use the provided outlines, YouTube URLs, news URLs, and headlines as the primary source material.
- Prefer facts that appear in the research or the user-provided material. Do not invent unsupported details.
- Do NOT repeat the same facts, details, or sentences. Each piece of information should appear only once.
- Write a clear, linear script that moves forward without looping or restating earlier points.
- Write ONLY the spoken script that a narrator would say. No director’s directions, stage directions, production notes, or bracketed text.
- Do not include any self-introduction unless the user specifically requests it.

Return only the final spoken script text."""
    response = openai_client.chat.completions.create(
        model=model, temperature=temperature,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def proofread_script(script: str, research: str, openai_client) -> str:
    prompt = f"""Strict fact-check the following script against the research.

Script:
{script}

Research:
{research}

Provide:
1. Unverified claims
2. Suggested fixes
3. Accuracy rating (High/Medium/Low)
4. Publish recommendation
Also note any obvious repetitions."""
    response = openai_client.chat.completions.create(
        model=model, temperature=0.1,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def process_audio(audio_bytes: bytes, style: str) -> bytes:
    AudioSegment, normalize, compress_dynamic_range = get_audio_tools()
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    
    if style == "Classic Trailer":
        new_sample_rate = int(audio.frame_rate * 0.89)
        audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_sample_rate})
        audio = audio.set_frame_rate(44100)
    
    try:
        audio = compress_dynamic_range(audio, threshold=-18.0, ratio=3.0, attack=5.0, release=50.0)
    except Exception:
        pass
    
    audio = normalize(audio)
    
    buffer = io.BytesIO()
    audio.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

def generate_tts(text: str, openai_client, voice: str, tts_model: str, style: str,
                 narrator_name: str, channel_name: str,
                 include_start_intro: bool, include_end_intro: bool) -> bytes:
    instructions = None
    if tts_model == "gpt-4o-mini-tts":
        intro_parts = []
        
        if include_start_intro and narrator_name.strip():
            channel_part = f" from {channel_name}" if channel_name.strip() else ""
            intro_parts.append(f"Start the recording by briefly introducing yourself once with the exact phrase 'I'm {narrator_name}{channel_part}.' After that single introduction, never introduce yourself or say your name again until the very end.")
        
        if include_end_intro and narrator_name.strip():
            channel_part = f" from {channel_name}" if channel_name.strip() else ""
            intro_parts.append(f"At the very end of the recording, after the main content is finished, introduce yourself once more with the exact phrase 'I'm {narrator_name}{channel_part}.' Do this only once at the end and nowhere else.")
        
        name_intro = " ".join(intro_parts)
        base_instruction = "Do not repeat sentences or facts. Do not introduce yourself except where specifically instructed."
        
        if style == "News Narrator":
            instructions = f"Speak in a clear, professional, neutral news-anchor style. Moderate pace, authoritative but calm and natural. {base_instruction} {name_intro}"
        elif style == "Classic Trailer":
            instructions = f"Speak in a deep, dramatic, cinematic movie-trailer narrator style. Low, resonant, powerful delivery with deliberate pacing. {base_instruction} {name_intro}"
    
    max_chars = 4000
    chunks = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    audio_parts = []
    
    for chunk in chunks:
        if chunk.strip():
            kwargs = {"model": tts_model, "voice": voice, "input": chunk, "response_format": "mp3"}
            if instructions:
                kwargs["instructions"] = instructions
            resp = openai_client.audio.speech.create(**kwargs)
            audio_parts.append(resp.content)
    
    combined = b"".join(audio_parts)
    return process_audio(combined, style)

# ── Session State ──────────────────────────────────────────────────
if "generated_script" not in st.session_state:
    st.session_state.generated_script = ""
if "voiceover_audio" not in st.session_state:
    st.session_state.voiceover_audio = None

# ── Generation ─────────────────────────────────────────────────────
if generate_btn:
    if not openai_key:
        st.error("OpenAI API key is required.")
    elif not any([proposed.strip(), youtube_urls.strip(), news_urls.strip(), headlines.strip()]):
        st.warning("Please provide at least one input (script/topic, YouTube URL, news URL, or headline).")
    else:
        with st.spinner("Researching and generating..."):
            try:
                OpenAI = get_openai()
                client = OpenAI(api_key=openai_key)
                
                user_request = build_user_request(proposed, youtube_urls, news_urls, headlines)
                
                research = "Research disabled."
                if use_research and serpapi_key:
                    # Use the first non-empty input as the research query
                    query_source = headlines or proposed or youtube_urls or news_urls
                    research = search_facts(query_source[:300], serpapi_key)
                
                if research_is_weak(research):
                    st.warning("Limited research available. Script will stay more general.")
                
                generated = generate_script(user_request, research, client)
                fact_check = proofread_script(generated, research, client)
                
                st.session_state.generated_script = generated
                st.session_state.fact_check = fact_check
                st.session_state.research = research
                st.session_state.voiceover_audio = None
                st.success("Script generated and checked!")
                
                st.subheader("Generated Script")
                st.text_area("Script", value=generated, height=400, key="script_display")
                
                with st.expander("🔍 Fact-Check Notes", expanded=True):
                    st.markdown(fact_check)
                with st.expander("Research Used"):
                    st.markdown(research or "None")
            except Exception as e:
                st.error(str(e))

if st.session_state.get("generated_script") and not generate_btn:
    st.subheader("Generated Script")
    st.text_area("Script", value=st.session_state.generated_script, height=400, key="script_display_persistent")
    if "fact_check" in st.session_state:
        with st.expander("🔍 Fact-Check Notes", expanded=False):
            st.markdown(st.session_state.fact_check)
    if "research" in st.session_state:
        with st.expander("Research Used"):
            st.markdown(st.session_state.research or "None")

# ── Voiceover Section ──────────────────────────────────────────────
if st.session_state.get("generated_script"):
    st.divider()
    st.subheader("🎙️ Voiceover Studio")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        tts_model = st.selectbox("TTS Model", ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"], index=2)
    with col2:
        base_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "ash", "coral", "sage"]
        extra_voices = ["ballad", "verse", "marin", "cedar"]
        available_voices = base_voices + extra_voices if tts_model == "gpt-4o-mini-tts" else base_voices
        voice = st.selectbox("Voice", available_voices, index=available_voices.index("onyx") if "onyx" in available_voices else 0)
    with col3:
        voice_style = st.selectbox("Voice Style", ["News Narrator", "Classic Trailer"], index=0)
    
    st.markdown("**Narrator Introduction Options**")
    include_start_intro = st.checkbox("Include introduction at the start", value=False)
    include_end_intro = st.checkbox("Include introduction at the very end", value=False)
    
    narrator_name = st.text_input(
        "Custom Narrator Name",
        placeholder="e.g. Alex Rivera",
        disabled=not (include_start_intro or include_end_intro),
    )
    
    channel_name = st.text_input(
        "Custom YouTube Channel Name (optional)",
        placeholder="e.g. Aviation Insights",
        disabled=not (include_start_intro or include_end_intro),
    )
    
    st.markdown("#### Preview Voice")
    preview_text = st.text_input("Preview text", value="This is a preview of the selected voice and style.")
    
    if st.button("▶️ Preview Selected Voice", use_container_width=True):
        with st.spinner("Generating preview..."):
            try:
                OpenAI = get_openai()
                client = OpenAI(api_key=openai_key)
                audio = generate_tts(preview_text, client, voice, tts_model, voice_style, narrator_name, channel_name, include_start_intro, include_end_intro)
                st.audio(audio, format="audio/mp3")
            except Exception as e:
                st.error(str(e))
    
    st.markdown("#### Full Voiceover")
    if st.button("🔊 Generate Full Voiceover MP3", type="primary", use_container_width=True):
        with st.spinner("Creating and processing voiceover..."):
            try:
                OpenAI = get_openai()
                client = OpenAI(api_key=openai_key)
                audio = generate_tts(st.session_state.generated_script, client, voice, tts_model, voice_style, narrator_name, channel_name, include_start_intro, include_end_intro)
                st.session_state.voiceover_audio = audio
                st.success("Voiceover generated, processed, and normalized!")
                st.audio(audio, format="audio/mp3")
            except Exception as e:
                st.error(str(e))
    
    if st.session_state.get("voiceover_audio") is not None:
        st.download_button(
            label="⬇️ Download MP3 Voiceover",
            data=st.session_state.voiceover_audio,
            file_name="youtube_voiceover.mp3",
            mime="audio/mp3",
            use_container_width=True
        )

st.markdown("---")
st.caption("You can now mix outlines, YouTube URLs, news URLs, and headlines. The script is generated on the fly from all provided sources.")
