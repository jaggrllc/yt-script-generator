import streamlit as st
from openai import OpenAI
import serpapi
import json

st.set_page_config(page_title="YouTube Script Generator", page_icon="🎬", layout="wide")

st.title("🎬 YouTube Video Script Generator")
st.caption("Generate + proofread YouTube scripts using OpenAI + SerpAPI fact-checking")

# ── Sidebar: API Keys ──────────────────────────────────────────────
with st.sidebar:
    st.header("API Keys")
    openai_key = st.text_input("OpenAI API Key", type="password", help="sk-...")
    serpapi_key = st.text_input("SerpAPI Key", type="password", help="From serpapi.com")
    
    st.divider()
    model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o", "gpt-4.1"], index=0)
    temperature = st.slider("Creativity", 0.0, 1.0, 0.7)
    
    st.markdown("---")
    st.markdown("**How to use**")
    st.markdown("1. Paste your proposed script or topic above")
    st.markdown("2. Click Generate")
    st.markdown("3. Review the polished script + fact-check below")

# ── Main Input ─────────────────────────────────────────────────────
proposed = st.text_area(
    "Proposed Video Script / Topic / Outline",
    height=200,
    placeholder="Paste your draft script, outline, or just the video topic here..."
)

col1, col2, col3 = st.columns(3)
with col1:
    tone = st.selectbox("Tone", ["Educational", "Conversational", "Storytelling", "Energetic", "Professional"])
with col2:
    length = st.selectbox("Target Length", ["3-5 min", "6-10 min", "11-15 min", "15+ min"])
with col3:
    style = st.selectbox("Style", ["Standard YouTube", "Tutorial", "Review", "Story", "Listicle"])

generate_btn = st.button("🚀 Generate & Proofread Script", type="primary", use_container_width=True)

# ── Generation Logic ───────────────────────────────────────────────
def search_facts(query: str, api_key: str) -> str:
    try:
        client = serpapi.Client(api_key=api_key)
        results = client.search({
            "engine": "google",
            "q": query,
            "num": 8,
            "hl": "en"
        })
        snippets = []
        for r in results.get("organic_results", [])[:6]:
            snippets.append(f"- {r.get('title', '')}: {r.get('snippet', '')}")
        return "\n".join(snippets) if snippets else "No strong search results found."
    except Exception as e:
        return f"SerpAPI error: {str(e)}"

def generate_script(proposed_text: str, research: str, openai_client: OpenAI) -> str:
    prompt = f"""You are an expert YouTube scriptwriter.

User input (topic, outline, or draft):
{proposed_text}

Tone: {tone}
Target length: {length}
Style: {style}

Real-time research (from Google via SerpAPI):
{research}

Write a complete, engaging YouTube video script that:
- Has a strong hook in the first 15 seconds
- Clear structure (Hook → Intro → Main Points → CTA)
- Natural spoken language
- Incorporates accurate facts from the research where relevant
- Avoids unverified claims

Return ONLY the script text."""

    response = openai_client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def proofread_script(script: str, research: str, openai_client: OpenAI) -> str:
    prompt = f"""Proofread this YouTube script and check for factual accuracy.

Script:
{script}

Research data:
{research}

Provide:
1. A short list of any potential errors, unverified claims, or weak facts
2. Suggested corrections
3. Overall accuracy rating (High / Medium / Low)

Be concise and practical."""

    response = openai_client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# ── Run Generation ─────────────────────────────────────────────────
if generate_btn:
    if not openai_key or not serpapi_key:
        st.error("Please enter both API keys in the sidebar.")
    elif not proposed.strip():
        st.warning("Please enter a topic or proposed script.")
    else:
        with st.spinner("Researching with SerpAPI + generating with OpenAI..."):
            try:
                client = OpenAI(api_key=openai_key)
                
                # Research
                research = search_facts(proposed[:200], serpapi_key)
                
                # Generate
                generated = generate_script(proposed, research, client)
                
                # Proofread
                fact_check = proofread_script(generated, research, client)
                
                # Display results
                st.success("Script generated and checked!")
                
                st.subheader("Generated YouTube Video Script")
                st.text_area(
                    "Generated Script (copy this)",
                    value=generated,
                    height=400,
                    key="generated_script"
                )
                
                with st.expander("🔍 Fact-Check & Proofreading Notes", expanded=True):
                    st.markdown(fact_check)
                
                with st.expander("Research Sources Used"):
                    st.markdown(research)
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.info("Check your API keys and try again.")

st.markdown("---")
st.caption("Tip: For Streamlit Cloud deployment, add keys to Secrets instead of the sidebar for better security.")
