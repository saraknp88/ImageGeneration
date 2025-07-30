import streamlit as st
import requests
import os
from PIL import Image
from io import BytesIO
import time
import base64

# Page configuration
st.set_page_config(
    page_title="✨ AI Image Generator",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main {
        padding-top: 2rem;
    }
    
    .stTextArea > div > div > textarea {
        font-size: 16px;
        border-radius: 10px;
    }
    
    .stButton > button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        font-weight: 600;
        font-size: 16px;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
    }
    
    .image-container {
        border-radius: 15px;
        padding: 20px;
        background: white;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        margin: 10px 0;
    }
    
    .success-message {
        padding: 10px;
        border-radius: 5px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        margin: 10px 0;
    }
    
    .error-message {
        padding: 10px;
        border-radius: 5px;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        margin: 10px 0;
    }
    
    .example-prompt {
        background: #f8f9fa;
        border-left: 4px solid #667eea;
        padding: 10px;
        margin: 5px 0;
        border-radius: 5px;
        cursor: pointer;
        transition: background 0.2s;
    }
    
    .example-prompt:hover {
        background: #e8f0fe;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'generated_images' not in st.session_state:
    st.session_state.generated_images = []
if 'generation_history' not in st.session_state:
    st.session_state.generation_history = []

def validate_api_key():
    """Check if OpenAI API key is available"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        st.error("⚠️ OpenAI API key not found! Please set the OPENAI_API_KEY environment variable.")
        st.info("To deploy on Streamlit Cloud, add your API key in the app settings under 'Secrets'.")
        st.code("""
# In Streamlit Cloud secrets:
OPENAI_API_KEY = "your_api_key_here"
        """)
        return False
    return True

def validate_prompt(prompt):
    """Validate and sanitize the input prompt"""
    if not prompt or len(prompt.strip()) < 10:
        return False, "Please provide a more detailed description (at least 10 characters)."
    
    if len(prompt) > 1000:
        return False, "Prompt is too long. Please keep it under 1000 characters."
    
    # Basic content filtering
    forbidden_words = ['nsfw', 'explicit', 'nude', 'violence', 'gore']
    prompt_lower = prompt.lower()
    
    for word in forbidden_words:
        if word in prompt_lower:
            return False, "Prompt contains inappropriate content. Please try a different description."
    
    return True, prompt.strip()

def generate_images_openai(prompt):
    """Generate images using OpenAI DALL-E API"""
    api_key = os.getenv('OPENAI_API_KEY')
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    data = {
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 2,  # Generate 2 images
        "size": "1024x1024",
        "quality": "standard",
        "response_format": "url"
    }
    
    try:
        response = requests.post(
            'https://api.openai.com/v1/images/generations',
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return True, [img['url'] for img in result['data']]
        
        elif response.status_code == 429:
            return False, "Rate limit exceeded. Please wait a moment before trying again."
        
        elif response.status_code == 400:
            error_data = response.json()
            if 'content_policy_violation' in str(error_data):
                return False, "Your prompt violates content policy. Please try a different description."
            return False, f"Invalid request: {error_data.get('error', {}).get('message', 'Unknown error')}"
        
        else:
            return False, f"API Error: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, "Request timed out. Please try again."
    
    except requests.exceptions.RequestException as e:
        return False, f"Network error: {str(e)}"
    
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def download_image(image_url, filename):
    """Create download button for image"""
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            return response.content
        return None
    except:
        return None

def main():
    # Header
    st.markdown("""
    <div style='text-align: center; padding: 2rem 0;'>
        <h1 style='background: linear-gradient(135deg, #667eea, #764ba2); 
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
                   font-size: 3rem; margin-bottom: 0.5rem;'>
            ✨ AI Image Generator
        </h1>
        <p style='font-size: 1.2rem; color: #666; margin-bottom: 2rem;'>
            Create stunning images with the power of AI
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check API key
    if not validate_api_key():
        return
    
    # Main input section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🎨 Describe Your Image")
        prompt = st.text_area(
            "Enter your prompt:",
            height=100,
            placeholder="Describe the image you want to generate in detail... The more specific you are, the better the results!",
            label_visibility="collapsed"
        )
        
        # Example prompts
        with st.expander("💡 Try these example prompts"):
            example_prompts = [
                "A majestic dragon soaring over a mystical forest at golden hour",
                "A cozy coffee shop in a cyberpunk city with neon lights reflecting on wet streets",
                "An astronaut painting on an easel on the surface of Mars, Earth visible in the sky",
                "A steampunk library with floating books and mechanical gears, warm golden lighting",
                "A serene Japanese garden with cherry blossoms and a traditional wooden bridge",
                "A futuristic city floating in the clouds with flying cars and glass towers"
            ]
            
            for example in example_prompts:
                if st.button(example, key=f"example_{hash(example)}"):
                    st.session_state.example_prompt = example
                    st.rerun()
        
        # Use example prompt if selected
        if 'example_prompt' in st.session_state:
            prompt = st.session_state.example_prompt
            del st.session_state.example_prompt
            st.rerun()
    
    with col2:
        st.markdown("### ⚙️ Settings")
        
        # Generation settings info
        st.info("""
        **Current Settings:**
        - Model: DALL-E 3
        - Images: 2 per generation
        - Size: 1024x1024
        - Quality: Standard
        """)
        
        # Usage tips
        st.markdown("### 💡 Tips for Better Results")
        st.markdown("""
        - Be specific and detailed
        - Include style, mood, lighting
        - Mention colors and composition
        - Add artistic styles (e.g., "watercolor", "photorealistic")
        """)
    
    # Generate button
    if st.button("🎨 Generate Images", type="primary"):
        if not prompt:
            st.error("Please enter a prompt to generate images.")
            return
        
        # Validate prompt
        is_valid, result = validate_prompt(prompt)
        if not is_valid:
            st.error(result)
            return
        
        # Show loading state
        with st.spinner("🎨 Creating your masterpieces... This may take 10-30 seconds"):
            progress_bar = st.progress(0)
            for i in range(100):
                time.sleep(0.1)
                progress_bar.progress(i + 1)
            
            # Generate images
            success, result = generate_images_openai(result)
            progress_bar.empty()
        
        if success:
            st.session_state.generated_images = result
            st.session_state.generation_history.insert(0, {
                'prompt': prompt,
                'images': result,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            })
            st.success("🎉 Images generated successfully!")
            st.rerun()
        else:
            st.error(f"❌ {result}")
    
    # Display generated images
    if st.session_state.generated_images:
        st.markdown("---")
        st.markdown("### 🖼️ Generated Images")
        
        cols = st.columns(2)
        for i, image_url in enumerate(st.session_state.generated_images):
            with cols[i % 2]:
                st.markdown(f"#### ✨ Image {i + 1}")
                
                try:
                    # Display image
                    st.image(image_url, use_column_width=True)
                    
                    # Download button
                    image_data = download_image(image_url, f"generated_image_{i+1}")
                    if image_data:
                        st.download_button(
                            label=f"💾 Download Image {i + 1}",
                            data=image_data,
                            file_name=f"ai_generated_image_{i+1}.png",
                            mime="image/png",
                            key=f"download_{i}"
                        )
                    
                except Exception as e:
                    st.error(f"Error loading image {i + 1}: {str(e)}")
    
    # Generation history sidebar
    if st.session_state.generation_history:
        with st.sidebar:
            st.markdown("### 📝 Recent Generations")
            
            for i, item in enumerate(st.session_state.generation_history[:5]):
                with st.expander(f"🕒 {item['timestamp']}", expanded=False):
                    st.write(f"**Prompt:** {item['prompt'][:100]}...")
                    if st.button(f"🔄 Regenerate", key=f"regen_{i}"):
                        st.session_state.example_prompt = item['prompt']
                        st.rerun()
            
            if st.button("🗑️ Clear History"):
                st.session_state.generation_history = []
                st.rerun()

if __name__ == "__main__":
    main()
