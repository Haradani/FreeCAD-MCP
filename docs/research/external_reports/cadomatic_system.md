# CADomatic: RAG-Powered FreeCAD Script Generation

## Executive Summary

CADomatic is an open-source system that generates parametric FreeCAD Python scripts from natural language descriptions using Retrieval-Augmented Generation (RAG). Unlike systems that generate static 3D models, CADomatic produces editable Python code that creates fully parametric CAD geometry with a proper design tree, enabling engineers to modify dimensions and iterate rapidly.

**Repository**: https://github.com/yas1nsyed/CADomatic
**HuggingFace Space**: https://huggingface.co/spaces/Yas1n/CADomatic
**Author**: Yasin Syed
**License**: MIT (implied from structure)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
│                    (Gradio Web Application)                          │
│  ┌─────────────────────┐    ┌─────────────────────────┐             │
│  │  "Generate New Part" │    │  "Edit Existing Part"   │             │
│  │  (resets memory)     │    │  (preserves context)    │             │
│  └──────────┬──────────┘    └────────────┬────────────┘             │
└─────────────┼────────────────────────────┼──────────────────────────┘
              │                            │
              ▼                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PROCESSING PIPELINE                               │
│                      (app/process.py)                                │
│                            │                                         │
│                            ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                 RAG RETRIEVAL SYSTEM                          │   │
│  │                  (src/llm_client.py)                          │   │
│  │                                                                │   │
│  │   ┌─────────────────┐     ┌─────────────────────────────┐    │   │
│  │   │  User Prompt    │────▶│  FAISS Vector Search        │    │   │
│  │   └─────────────────┘     │  (sentence-transformers/    │    │   │
│  │                           │   all-MiniLM-L6-v2)         │    │   │
│  │                           │   k=15 nearest chunks       │    │   │
│  │                           └──────────────┬──────────────┘    │   │
│  │                                          │                    │   │
│  │                                          ▼                    │   │
│  │                           ┌─────────────────────────────┐    │   │
│  │                           │  Retrieved FreeCAD Wiki     │    │   │
│  │                           │  Documentation Chunks       │    │   │
│  │                           │  (~2000 pages crawled)      │    │   │
│  │                           └──────────────┬──────────────┘    │   │
│  └───────────────────────────────────────────┼──────────────────┘   │
│                                              │                       │
│                                              ▼                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                 PROMPT CONSTRUCTION                           │   │
│  │                                                                │   │
│  │   ┌─────────────────────────────────────────────────────┐    │   │
│  │   │  System Instructions (base_instruction.txt)          │    │   │
│  │   │  + Retrieved Documentation Context                   │    │   │
│  │   │  + Conversation History (if editing)                 │    │   │
│  │   │  + User's Current Instruction                        │    │   │
│  │   └─────────────────────────────────────────────────────┘    │   │
│  │                            │                                  │   │
│  └────────────────────────────┼──────────────────────────────────┘   │
│                               │                                      │
│                               ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                 LLM GENERATION                                │   │
│  │                 (Gemini 2.5 Flash)                            │   │
│  │                                                                │   │
│  │   Temperature: 0.7                                            │   │
│  │   Output: Pure Python code, no comments                       │   │
│  │   Memory: ConversationBufferMemory for multi-turn             │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                               │                                      │
│                               ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                 POST-PROCESSING                               │   │
│  │                                                                │   │
│  │   • Strip markdown code fences (```python)                   │   │
│  │   • Append GUI view commands                                  │   │
│  │   • Save to generated/result_script.py                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          OUTPUT                                      │
│                                                                      │
│   • Python script preview in Gradio UI                              │
│   • Downloadable .py file                                           │
│   • Executable in FreeCAD Python console                            │
│   • Full parametric design tree                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Deep Dive

### 1. RAG Vector Store Builder (`src/rag_builder.py`)

The RAG system is built by crawling FreeCAD documentation:

```python
# Sources crawled
BASE_URL_WIKI = "https://wiki.freecad.org/Power_users_hub"
BASE_URL_GITHUB = "https://github.com/shaise/FreeCAD_FastenersWB"

# Crawl limits
wiki_pages = crawl_wiki(BASE_URL_WIKI, max_pages=2000)
github_pages = crawl_wiki(BASE_URL_GITHUB, max_pages=450)

# Text processing
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150
)

# Embeddings
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# Vector store
vectorstore = FAISS.from_documents(docs, embeddings)
```

**Key Features**:
- Excludes non-English pages (detects `/de`, `/fr`, `/es`, etc. in URLs)
- Excludes images and edit sections
- Checkpoints every 500 pages for crash recovery
- Pre-built vectorstore hosted on HuggingFace: `Yas1n/CADomatic_vectorstore`

### 2. LLM Client (`src/llm_client.py`)

```python
# Gemini 2.5 Flash configuration
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7,
    api_key=GEMINI_API_KEY
)

# Retrieval settings
retriever = vectorstore.as_retriever(search_kwargs={"k": 15})

# Conversation memory for multi-turn editing
memory = ConversationBufferMemory(return_messages=True)
```

**Prompt Construction**:
```python
def build_prompt(user_prompt: str) -> str:
    docs = retriever.invoke(user_prompt)
    context = "\n\n".join(doc.page_content for doc in docs)

    return f"""
You are a helpful assistant that writes FreeCAD Python scripts...

Use the following FreeCAD wiki documentation as context:
{context}

Here are a few important instructions for you to follow:
{BASE_INSTRUCTIONS}

Here is the conversation so far:
{history_text}

Current instruction:
{user_prompt}

Respond with valid FreeCAD 1.0.1 Python code only, no extra comments.
"""
```

### 3. Base Instructions (`prompts/base_instruction.txt`)

The base instructions file contains **critical FreeCAD-specific guidance** that prevents common LLM mistakes:

#### Import Patterns
```python
# CORRECT - always use these patterns
from FreeCAD import Vector
from FreeCAD import Placement
from FreeCAD import Rotation

# WRONG - will cause errors
import FreeCAD.Vector
```

#### API Corrections
| Wrong | Correct |
|-------|---------|
| `Part.Union(parts)` | `shape1.fuse(shape2)` |
| `Part.makeTube(radius, height)` | Create cylinder, cut inner cylinder |
| `bspline.toWire()` | `Part.Wire([bspline.toShape()])` |
| `Part.makeEllipse()` | `Part.Ellipse()` + set radii + `.toShape()` |
| `makeSweep()` | `path_wire.makePipeShell([profiles], ...)` |

#### Design Principles
- Use Part workbench, not PartDesign workbench
- Create proper design tree (each feature separately)
- Make designs modular (e.g., cup body + handle as separate features)
- No comments in generated code (reduce tokens)
- Always make generated objects visible

#### Few-Shot Examples

The instructions include complete working examples for:

1. **Flange** (~80 lines) - Demonstrates:
   - Parametric dimensions at top
   - Sequential boolean cuts for bolt holes
   - Proper design tree structure

2. **Teapot** (~120 lines) - Demonstrates:
   - BSpline curves for organic shapes
   - Revolve operations
   - Pipe sweeps for spout/handle
   - Multi-part fusion

3. **Herringbone Gear** (~200+ lines) - Demonstrates:
   - Complex parametric geometry
   - Lofting operations
   - Helical patterns

---

## Data Flow Analysis

### New Part Generation

```
User Input: "Create a flange with OD 100mm, bore 50mm, 6 M8 holes at PCD 75mm"
           │
           ▼
┌─────────────────────────────────────────┐
│ reset_memory()  # Clear conversation    │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ FAISS Search: k=15 relevant chunks      │
│ Retrieved: [flange examples, boolean    │
│            operations, Part::Cylinder]  │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Construct prompt:                       │
│ - Base instructions (~400 lines)        │
│ - Retrieved context (~15 chunks)        │
│ - User instruction                      │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Gemini 2.5 Flash generates Python code  │
│ Temperature: 0.7                        │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Post-process:                           │
│ - Strip ```python markers               │
│ - Add GUI view commands                 │
│ - Save to generated/result_script.py   │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Output: 100-line parametric Python      │
│ script with full design tree            │
└─────────────────────────────────────────┘
```

### Edit Existing Part

```
Previous: Flange script in memory
User Input: "Add a chamfer to the outer edge"
           │
           ▼
┌─────────────────────────────────────────┐
│ Keep memory (don't reset)               │
│ History: [User: flange, AI: script]     │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ FAISS Search: k=15 relevant chunks      │
│ Retrieved: [chamfer operations,         │
│            Part::Chamfer, edge refs]    │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Construct prompt with conversation:     │
│ User: Create flange...                  │
│ Assistant: [previous script]            │
│ User: Add chamfer to outer edge         │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Gemini generates modified script        │
│ (contextually aware of previous work)   │
└─────────────────────────────────────────┘
```

---

## Example Generated Output

**Input**: "Create a ball bearing with inner diameter 25mm, outer diameter 52mm, width 15mm, and 8 balls"

**Output** (abbreviated):
```python
import FreeCAD as App
import FreeCADGui as Gui
from FreeCAD import Vector, Placement, Rotation
import Part
import math

def createBearing():
    doc = App.newDocument("Bearing")

    # === Parameters (fully editable in design tree) ===
    INNER_RING_INNER_DIAMETER = 25.0
    INNER_RING_OUTER_DIAMETER = 35.0
    OUTER_RING_INNER_DIAMETER = 45.0
    OUTER_RING_OUTER_DIAMETER = 52.0
    BEARING_WIDTH = 15.0
    BALL_DIAMETER = 7.0
    NUMBER_OF_BALLS = 8

    # === Outer Ring ===
    outer_ring_outer_cyl = doc.addObject("Part::Cylinder", "OuterRing_OuterCylinder")
    outer_ring_outer_cyl.Radius = OUTER_RING_RADIUS_OUTER
    outer_ring_outer_cyl.Height = BEARING_WIDTH

    outer_ring_inner_cyl = doc.addObject("Part::Cylinder", "OuterRing_InnerBore")
    # ... boolean cut creates hollow ring

    # === Inner Ring (same pattern) ===
    # ...

    # === Balls (parametric placement) ===
    for i in range(NUMBER_OF_BALLS):
        angle_deg = 360 * i / NUMBER_OF_BALLS
        angle_rad = math.radians(angle_deg)
        x = PCD_BALLS * math.cos(angle_rad)
        y = PCD_BALLS * math.sin(angle_rad)

        ball = doc.addObject("Part::Sphere", f"Ball_{i+1:02d}")
        ball.Radius = BALL_RADIUS
        ball.Placement.Base = Vector(x, y, BEARING_WIDTH / 2)

    # === Cage with pockets ===
    # ...

    doc.recompute()
    return doc

if __name__ == "__main__":
    createBearing()
```

**Key Characteristics**:
- All dimensions as named constants at top
- Each component as separate Part:: object
- Sequential boolean operations with named cuts
- Parametric patterns (for loops for repeated features)
- No comments (token optimization)
- Proper design tree structure

---

## Integration Opportunities for FreeCAD MCP

### 1. Direct Integration: `generate_from_description` Tool

Add a new MCP tool that uses CADomatic's approach:

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "generate_from_description":
        description = arguments["description"]

        # 1. RAG retrieval
        docs = retriever.invoke(description)
        context = "\n\n".join(doc.page_content for doc in docs)

        # 2. Build prompt with base instructions
        prompt = build_freecad_prompt(description, context)

        # 3. Generate code
        code = await generate_with_llm(prompt)

        # 4. Execute in FreeCAD via XML-RPC
        result = client.execute_code(code)

        return [TextContent(type="text", text=f"Generated and executed script")]
```

### 2. Enhanced RAG with MCP Context

Combine CADomatic's FreeCAD wiki knowledge with:
- Current document state from MCP tools
- Previous conversation history
- User's design preferences

### 3. Iterative Design Loop

```
User: "Create a flange"
  │
  ├──▶ generate_from_description → Creates flange
  │
  ├──▶ get_view → Shows result image to AI
  │
  ├──▶ VLM analysis → "The bore is too small"
  │
  └──▶ generate_from_description → "Make the bore 20% larger"
```

### 4. Vectorstore Enhancement

Build extended vectorstore with:
- FreeCAD wiki (CADomatic's 2000 pages)
- FreeCAD Python API reference
- Example scripts from forums
- User's own successful scripts

---

## Dependencies

```
langchain-community
langchain-google-genai
langchain-huggingface
faiss-cpu
sentence-transformers
huggingface_hub
python-dotenv
gradio
beautifulsoup4
requests
```

---

## Limitations & Considerations

1. **FreeCAD Version**: Targets FreeCAD 1.0.x specifically
2. **Part vs PartDesign**: Only generates Part workbench code (not parametric PartDesign)
3. **GUI Commands**: Generated code includes `FreeCADGui` calls (won't work headless)
4. **Token Limits**: Large prompts with 15 RAG chunks + examples
5. **No Validation**: Generated code isn't validated before output
6. **Single Document**: Always creates new document, doesn't work with existing

---

## Recommendations for FreeCAD MCP Integration

1. **Adopt the RAG approach** - The vectorstore of FreeCAD wiki docs significantly improves code quality

2. **Use the base instructions** - The error corrections (fuse vs Union, import patterns) are invaluable

3. **Add code validation** - Execute generated code in sandbox, validate before returning

4. **Support headless mode** - Strip GUI commands when running in Docker container

5. **Extend to PartDesign** - Add examples for parametric sketch-based modeling

6. **Add visual feedback loop** - Generate → Render → VLM check → Iterate
