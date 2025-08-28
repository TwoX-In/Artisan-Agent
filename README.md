# 🎨 Artisan Agent

An intelligent multi-agent system powered by Google's ADK (Ads Development Kit) that creates comprehensive digital marketing assets for artisan products. The system coordinates specialized sub-agents to generate compelling stories, enhance images, and create promotional videos from product descriptions and images.

## 🏗️ Architecture Overview

The Artisan Agent follows a **coordinator-worker pattern** with a main orchestrator that delegates tasks to specialized sub-agents:

```
📋 Artisan Coordinator (Main Agent)
├── 📖 Story Agent     - Content & narrative creation
├── 🖼️  Image Agent    - Image enhancement & refinement  
└── 🎬 Video Agent     - Video generation from images
```

### Core Components

- **🧠 Main Coordinator**: Orchestrates the workflow and manages sub-agent interactions
- **⚡ Sub-Agents**: Specialized agents for specific content creation tasks
- **🔧 Google ADK Integration**: Leverages Google's agent development framework
- **☁️ Google Cloud Services**: Uses Vertex AI, Imagen, Veo, and Cloud Storage

## 🤖 Agent Breakdown

### 📋 Artisan Coordinator 
**Role**: Main orchestrator and workflow manager  
**Model**: `gemini-2.5-pro`  
**Responsibilities**:
- Receives user requests and product information
- Delegates tasks to appropriate sub-agents
- Coordinates the creation workflow
- Returns structured JSON responses with all generated assets

**Input**: Product description + stored GCS image URI  
**Output**: Structured JSON with story, videos, and enhanced content

---

### 📖 Story Agent
**Role**: Content creation specialist  
**Model**: `gemini-2.5-pro`  
**Tools**: Google Search API  

**Capabilities**:
- Generates compelling product descriptions
- Researches historical and cultural context
- Creates educational background stories
- Develops comprehensive FAQ sections
- Performs location-specific research for regional crafts

**Output Format**:
```json
{
  "product_description": "Enhanced marketing copy",
  "location_specific_info": "Regional/cultural context", 
  "descriptive_history": "Craft history and significance",
  "faqs": [{"question": "...", "answer": "..."}]
}
```

---

### 🎬 Video Agent  
**Role**: Video generation specialist  
**Model**: `gemini-2.5-pro` (orchestration) + `veo-3.0-generate-preview` (generation)  
**Integration**: Google's Veo model via Vertex AI

**Capabilities**:
- Generates 8-10 second promotional videos from product images
- Creates cinematic showcases highlighting craftsmanship
- Supports 16:9 aspect ratio (standard format)
- Handles GCS image input and output storage
- Includes timeout protection and progress monitoring

**Technical Specs**:
- **Duration**: 8-10 seconds (Veo model limit)
- **Aspect Ratio**: 16:9 (landscape)
- **Input**: GCS image URI + creative prompt
- **Output**: Generated video stored in GCS bucket

---

### 🖼️ Image Agent *(Currently Disabled)*
**Role**: Image enhancement specialist  
**Model**: `gemini-2.5-pro` + `imagen-3.0-capability-001`  

**Planned Capabilities**:
- Enhance image quality and clarity
- Adjust lighting and color balance  
- Remove noise and improve sharpness
- Preserve artisan craftsmanship details
- Maintain authentic product appearance

## 🎯 System Capabilities

The Artisan Agent system provides end-to-end digital marketing asset creation for artisan products through intelligent coordination of specialized sub-agents.

## 🧪 Testing

Run the test suite to verify your setup:

```bash
# Test environment configuration
python3 check_env.py

# Test basic video generation
python3 tests/simple_video_test.py

# Test with specific image
python3 tests/test_specific_image.py

# Full test suite
python3 tests/test_video_generation.py
```

## 📁 Project Structure

```
Artisan-Agent/
├── artisan_agent/              # Main agent package
│   ├── agent.py                # Coordinator agent
│   ├── prompt.py               # Main orchestration prompts
│   └── sub_agents/             # Specialized sub-agents
│       ├── artisan_story/      # Content creation agent
│       ├── artisan_image/      # Image enhancement agent
│       └── artisan_video/      # Video generation agent
├── tests/                      # Test scripts
├── requirements.txt            # Python dependencies
├── .env.template              # Environment template
├── SETUP_VIDEO_GENERATION.md  # Detailed setup guide
└── README.md                  # This file
```

## 🔧 Technical Details

### Models Used
- **Orchestration**: `gemini-2.5-pro` for reasoning and coordination
- **Video Generation**: `veo-3.0-generate-preview` for video creation
- **Image Enhancement**: `imagen-3.0-capability-001` for image editing
- **Search**: Google Search API for research

### Limitations
- **Video Duration**: 8-10 seconds maximum (Veo model constraint)
- **Aspect Ratio**: 16:9 only for video generation
- **Image Agent**: Currently disabled in coordinator
- **Cost**: ~$0.50-1.00 per video generation

### Error Handling
- Comprehensive timeout protection (10 minutes for video generation)
- Detailed error messages with troubleshooting guidance
- Graceful fallbacks for API failures
- Environment validation and setup verification

## 🎨 Use Cases

- **Artisan Marketplaces**: Generate rich product listings
- **E-commerce Platforms**: Create comprehensive product pages  
- **Social Media**: Generate promotional content and videos
- **Cultural Preservation**: Document traditional crafts and techniques
- **Educational Content**: Create informative material about artisan products
