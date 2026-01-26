# Media Metrics and Analysis System

## Overview

The media metrics system provides comprehensive analysis tools for images and videos, including:

- **Image Quality Metrics**: Entropy, variance, sharpness, usability assessment
- **Color Analysis**: Dominant colors, natural language color names, hue profiles
- **Video Motion Analysis**: Frame differencing, stuck detection, motion timelines
- **Automatic Analysis**: On-capture and on-create analysis integration

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MCP Server (Host)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Media Analysis Tools                          │    │
│  │  analyze_image_colors │ analyze_video_colors │ analyze_video_motion  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│       ┌────────────────────────────┼────────────────────────────┐           │
│       ▼                            ▼                            ▼           │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │ color_analyzer  │     │ cosmos_vlm      │     │ mcp_server      │       │
│  │ (color_analyzer │     │ (image quality) │     │ (motion         │       │
│  │  .py)           │     │                 │     │  analysis)      │       │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Image Quality Metrics

### compute_image_quality (in cosmos_vlm.py)

Validates images before VLM inference to prevent hallucinations on blank/low-quality frames.

```python
@staticmethod
def compute_image_quality(image: "Image.Image") -> Dict[str, Any]:
    """Compute image quality metrics to detect black/empty/low-information images.

    Returns metrics with natural language descriptions:
    - entropy: Information content (0.0=uniform, 8.0=maximum)
    - variance: Pixel variance (low = uniform color)
    - mean: Average pixel value
    - quality_level: Human-readable assessment
    """
```

**Algorithm:**

```python
# Convert to grayscale numpy array
gray = np.array(image.convert("L"), dtype=np.float32)

# Compute basic statistics
mean_val = float(np.mean(gray))
variance = float(np.var(gray))
std_dev = float(np.std(gray))
min_val = float(np.min(gray))
max_val = float(np.max(gray))

# Compute entropy (information content)
hist, _ = np.histogram(gray.flatten(), bins=256, range=(0, 256))
hist = hist / hist.sum()  # Normalize
hist = hist[hist > 0]  # Remove zeros for log
entropy = float(-np.sum(hist * np.log2(hist))) if len(hist) > 0 else 0.0
```

**Quality Levels:**

| Level | Variance | Entropy | Description |
|-------|----------|---------|-------------|
| `blank` | < 1.0 | any | Completely blank (all pixels identical) |
| `near_blank` | any | < 0.3 | Almost no visual information |
| `very_low` | any | 0.3 - 0.5 | Mostly uniform image |
| `low` | any | 0.5 - 1.0 | Simple scene with limited detail |
| `moderate` | any | 1.0 - 2.0 | Some visual detail present |
| `good` | any | 2.0 - 4.0 | Clear visual content |
| `high` | any | 4.0+ | Rich visual detail |

**Quality Descriptions (Human-readable):**

```python
quality_descriptions = {
    "blank": "Image is completely blank (all pixels identical). No visual content detected.",
    "near_blank": "Image is nearly blank (entropy < 0.3). Almost no visual information.",
    "very_low": "Very low information content (entropy 0.3-0.5). Likely a mostly uniform image.",
    "low": "Low information content (entropy 0.5-1.0). Simple scene with limited detail.",
    "moderate": "Moderate information content (entropy 1.0-2.0). Some visual detail present.",
    "good": "Good information content (entropy 2.0-4.0). Clear visual content.",
    "high": "High information content (entropy 4.0+). Rich visual detail.",
}
```

**Output Example:**

```json
{
    "entropy": 4.235,
    "variance": 2847.5,
    "std_dev": 53.4,
    "mean": 127.3,
    "min": 0.0,
    "max": 255.0,
    "quality_level": "high",
    "quality_description": "High information content (entropy 4.0+). Rich visual detail.",
    "is_usable": true
}
```

## Color Analysis System

### Color Analyzer Module (color_analyzer.py)

Provides detailed color analysis with natural language names based on:
- CIE L*a*b* color space for perceptual uniformity
- 128-bin hex quantization for efficient clustering
- Berlin-Kay basic color terms hierarchy
- XKCD Color Survey (3.25M color-name judgments)

### Color Space Conversions

```python
def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB to hex string."""
    return f"#{r:02X}{g:02X}{b:02X}"

def rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert RGB (0-255) to HSV (0-1 for each component)."""
    return colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

def rgb_to_lab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert RGB to CIE L*a*b* color space.
    Uses D65 illuminant (standard daylight).
    Returns L* (0-100), a* (-128 to 127), b* (-128 to 127).
    """
```

### Color Quantization

Reduces colors to ~125 bins for efficient analysis:

```python
def quantize_to_128_bins(r: int, g: int, b: int) -> Tuple[int, int, int]:
    """Quantize RGB color to 128 bins (5 levels per channel = 125 colors).

    Uses levels: 0, 64, 128, 192, 255 per channel.
    """
    def quantize_channel(c):
        if c < 32:
            return 0
        elif c < 96:
            return 64
        elif c < 160:
            return 128
        elif c < 224:
            return 192
        else:
            return 255

    return (quantize_channel(r), quantize_channel(g), quantize_channel(b))
```

### Basic Color Terms (Berlin-Kay Hierarchy)

```python
BASIC_COLOR_TERMS = {
    # Achromatic
    "white": {"rgb": (255, 255, 255), "hsv_ranges": {"s": (0, 0.1), "v": (0.9, 1.0)}},
    "black": {"rgb": (0, 0, 0), "hsv_ranges": {"s": (0, 1), "v": (0, 0.15)}},
    "gray": {"rgb": (128, 128, 128), "hsv_ranges": {"s": (0, 0.15), "v": (0.15, 0.9)}},
    # Chromatic (Berlin-Kay basic terms)
    "red": {"rgb": (255, 0, 0), "hue_range": (345, 15)},  # wraps around
    "orange": {"rgb": (255, 165, 0), "hue_range": (15, 45)},
    "yellow": {"rgb": (255, 255, 0), "hue_range": (45, 70)},
    "green": {"rgb": (0, 128, 0), "hue_range": (70, 165)},
    "cyan": {"rgb": (0, 255, 255), "hue_range": (165, 195)},
    "blue": {"rgb": (0, 0, 255), "hue_range": (195, 260)},
    "purple": {"rgb": (128, 0, 128), "hue_range": (260, 290)},
    "magenta": {"rgb": (255, 0, 255), "hue_range": (290, 330)},
    "pink": {"rgb": (255, 192, 203), "hue_range": (330, 345)},
    # Extended common terms
    "brown": {"rgb": (139, 69, 19), "special": "low_saturation_orange_red"},
    "beige": {"rgb": (245, 245, 220), "special": "desaturated_yellow"},
    "teal": {"rgb": (0, 128, 128), "hue_range": (170, 190)},
    "navy": {"rgb": (0, 0, 128), "special": "dark_blue"},
    "maroon": {"rgb": (128, 0, 0), "special": "dark_red"},
    "olive": {"rgb": (128, 128, 0), "special": "dark_yellow_green"},
}
```

### Color Modifiers

**Lightness Modifiers (based on HSV Value):**

| Modifier | Value Range |
|----------|-------------|
| "very dark" | 0.0 - 0.25 |
| "dark" | 0.25 - 0.45 |
| (none) | 0.45 - 0.75 |
| "light" | 0.75 - 0.9 |
| "very light" | 0.9 - 1.0 |

**Saturation Modifiers (based on HSV Saturation):**

| Modifier | Saturation Range |
|----------|------------------|
| "grayish" | 0.0 - 0.2 |
| "muted" | 0.2 - 0.4 |
| (none) | 0.4 - 0.7 |
| "vivid" | 0.7 - 0.85 |
| "bright" | 0.85 - 1.0 |

### Natural Language Color Naming

```python
def generate_color_name(r: int, g: int, b: int) -> Tuple[str, str, List[str]]:
    """Generate a natural language color name from RGB values.

    Returns:
        Tuple of (base_name, full_name, modifiers)
        e.g., ("orange", "vivid dark orange", ["vivid", "dark"])
    """
```

**Example Names:**
- "vivid orange" - high saturation orange
- "dark muted blue" - dark, desaturated blue
- "light pink" - high value, desaturated red
- "very dark gray" - very low value, low saturation

### Color Diversity Score

Entropy-based diversity calculation:

```python
# Calculate color diversity (entropy)
entropy = 0.0
for color in colors:
    p = color.pixel_count / total_pixels
    if p > 0:
        entropy -= p * math.log2(p)

# Normalize entropy (max entropy for N colors is log2(N))
max_entropy = math.log2(len(colors)) if len(colors) > 1 else 1
diversity = entropy / max_entropy if max_entropy > 0 else 0
```

**Diversity Score Interpretation:**
- 0.0: Single dominant color
- 0.5: Moderate color variety
- 1.0: Maximum diversity (all colors equal)

### Dominant Hue Profile

Categorizes overall image tone:

```python
warm_count = sum(c.pixel_count for c in colors
                 if c.base_name in ("red", "orange", "yellow", "brown", "pink"))
cool_count = sum(c.pixel_count for c in colors
                 if c.base_name in ("blue", "cyan", "teal", "purple", "green"))
neutral_count = sum(c.pixel_count for c in colors
                    if c.base_name in ("white", "black", "gray", "beige"))

if neutral_count > warm_count and neutral_count > cool_count:
    dominant_hue = "neutral"
elif warm_count > cool_count * 1.5:
    dominant_hue = "warm"
elif cool_count > warm_count * 1.5:
    dominant_hue = "cool"
else:
    dominant_hue = "mixed"
```

## MCP Tools

### analyze_image_colors

```python
@mcp.tool()
def analyze_image_colors(
    image_path: str,
    top_n: int = 16,
    min_percentage: float = 0.5,
) -> str:
    """Analyze the dominant colors in an image with natural language descriptions.

    Args:
        image_path: Path to the image file (JPEG, PNG, etc.)
        top_n: Maximum number of colors to return (default: 16)
        min_percentage: Minimum percentage threshold (default: 0.5%)

    Returns:
        JSON string with:
        - summary: Natural language summary of dominant colors
        - dominant_hue: Overall color tone (warm, cool, neutral, mixed)
        - color_diversity: Entropy-based diversity score (0-1)
        - colors: List of colors with names, hex values, RGB, percentages
    """
```

**Example Output:**

```json
{
    "summary": "Predominantly gray (45.2%), with dark blue and muted green accents. Overall tone: cool.",
    "dominant_hue": "cool",
    "color_diversity": 0.734,
    "total_pixels": 307200,
    "unique_colors_detected": 15234,
    "quantized_colors": 87,
    "colors": [
        {
            "name": "gray",
            "base_name": "gray",
            "hex": "#808080",
            "rgb": [128, 128, 128],
            "percentage": 45.2,
            "pixel_count": 138854,
            "modifiers": []
        },
        {
            "name": "dark blue",
            "base_name": "blue",
            "hex": "#000040",
            "rgb": [0, 0, 64],
            "percentage": 22.1,
            "pixel_count": 67891,
            "modifiers": ["dark"]
        }
    ]
}
```

### analyze_video_colors

```python
@mcp.tool()
def analyze_video_colors(
    video_path: str,
    top_n: int = 16,
    min_percentage: float = 0.5,
    sample_fps: float = 2.0,
    max_frames: int = 60,
) -> str:
    """Analyze colors across a video with first, all (averaged), and last frame stats.

    Returns:
        JSON string with:
        - Video metadata (fps, duration, frames analyzed)
        - first_frame: Color analysis of the first frame
        - all_frames: Aggregated color analysis across sampled frames
        - last_frame: Color analysis of the last frame
        - Change detection (colors added, removed, increased, decreased)
        - overall_shift: Direction of color change (warmer, cooler, etc.)
    """
```

**Example Output:**

```json
{
    "total_frames": 150,
    "frames_analyzed": 30,
    "fps": 30.0,
    "duration_seconds": 5.0,
    "change_summary": "Increased: orange (5.2% → 12.3%) | New colors: yellow (+3.1%)",
    "overall_shift": "warmer, more saturated",
    "colors_added": ["yellow (+3.1%)"],
    "colors_removed": [],
    "colors_increased": ["orange (5.2% → 12.3%)"],
    "colors_decreased": ["gray (45.2% → 38.1%)"],
    "first_frame": { ... },
    "all_frames": { ... },
    "last_frame": { ... }
}
```

### analyze_video_motion

```python
@mcp.tool()
def analyze_video_motion(
    video_path: str,
    sample_fps: float = 4.0,
    motion_threshold: int = 25,
    min_motion_area: float = 0.5,
) -> str:
    """Analyze motion between frames in a video using frame differencing.

    Args:
        video_path: Path to the video file (MP4, AVI, etc.)
        sample_fps: Frame sampling rate for analysis (default: 4 fps)
        motion_threshold: Pixel difference threshold 0-255 (default: 25)
        min_motion_area: Minimum percentage of changed pixels (default: 0.5%)

    Returns:
        JSON string with:
        - motion_detected: Whether any significant motion was detected
        - total_frames: Number of frames analyzed
        - frames_with_motion: Number of frames showing motion
        - motion_percentage: Percentage of frames with motion
        - avg_motion_area: Average percentage of pixels changing
        - max_motion_area: Maximum motion area detected
        - stuck_detected: True if robot appears frozen (<20% motion)
    """
```

**Algorithm:**

```python
# Frame differencing algorithm
prev_gray = None
motion_values = []

for frame in sampled_frames:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    if prev_gray is not None:
        frame_diff = cv2.absdiff(prev_gray, gray)
        _, thresh = cv2.threshold(frame_diff, motion_threshold, 255, cv2.THRESH_BINARY)
        motion_pixels = np.count_nonzero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        motion_percent = (motion_pixels / total_pixels) * 100
        motion_values.append(motion_percent >= min_motion_area)

    prev_gray = gray

# Detect "stuck" state (no motion in >80% of frames)
stuck_detected = motion_percentage < 20
```

**Example Output:**

```json
{
    "motion_detected": true,
    "total_frames": 40,
    "frames_with_motion": 34,
    "motion_percentage": 85.0,
    "avg_motion_area": 4.2,
    "max_motion_area": 12.5,
    "motion_timeline": [true, true, true, false, true, ...],
    "stuck_detected": false,
    "video_fps": 30.0,
    "duration_seconds": 3.5
}
```

### analyze_camera_colors

```python
@mcp.tool()
def analyze_camera_colors(
    camera_name: str = None,
    top_n: int = 16,
    min_percentage: float = 0.5,
) -> str:
    """Capture a frame from an Isaac Sim camera and analyze its colors.

    Combines get_camera_frame and analyze_image_colors into a single tool.
    """
```

## Automatic Analysis Integration

### On-Capture Analysis (Images)

When capturing frames with `get_camera_frame`:

```python
# In get_camera_frame():
if analyze_on_capture:
    from PIL import Image as PILImage
    img = PILImage.open(image_path)
    quality = CosmosVLM.compute_image_quality(img)
    result["image_quality"] = quality
```

### On-Create Analysis (Videos)

When creating videos with `create_video_from_frames`:

```python
# In create_video_from_frames():
if analyze_on_create:
    motion_result = _analyze_video_motion_internal(output_path, sample_fps=4)
    if motion_result:
        result["motion_analysis"] = motion_result
```

### Auto-Prepended Motion Context (VLM)

When querying VLM about videos:

```python
# In vlm_query_video():
if include_motion_context:
    motion_result = analyze_video_motion(video_path, sample_fps=fps)
    if motion_result.get("motion_detected"):
        motion_summary = f"""
Motion Analysis Summary:
- Motion detected: Yes
- Frames with motion: {motion_result['frames_with_motion']}/{motion_result['total_frames']}
- Average motion area: {motion_result['avg_motion_area']:.1f}%
"""
        prompt = motion_summary + "\n\n" + prompt
```

## Data Classes

### ColorInfo

```python
@dataclass
class ColorInfo:
    """Information about a single color."""

    hex_value: str  # e.g., "#FF5733"
    rgb: Tuple[int, int, int]  # (255, 87, 51)
    hsv: Tuple[float, float, float]  # (0.05, 0.8, 1.0)
    lab: Optional[Tuple[float, float, float]] = None

    # Natural language descriptions
    base_name: str = ""  # e.g., "red", "blue"
    full_name: str = ""  # e.g., "vivid orange-red"
    modifiers: List[str] = field(default_factory=list)

    # Quantization info
    bin_index: int = 0  # 0-124 for 125-bin quantization
    bin_hex: str = ""  # Quantized hex value

    # Statistics
    pixel_count: int = 0
    percentage: float = 0.0
```

### ColorAnalysisResult

```python
@dataclass
class ColorAnalysisResult:
    """Result of color analysis for an image or video frame."""

    colors: List[ColorInfo] = field(default_factory=list)

    # Summary statistics
    total_pixels: int = 0
    unique_colors: int = 0  # Before quantization
    quantized_colors: int = 0  # After quantization

    # Overall color profile
    dominant_hue: Optional[str] = None  # "warm", "cool", "neutral", "mixed"
    color_diversity: float = 0.0  # Entropy-based score (0-1)

    # Natural language summary
    summary: str = ""
```

### VideoColorAnalysis

```python
@dataclass
class VideoColorAnalysis:
    """Complete color analysis for a video."""

    first_frame: ColorAnalysisResult
    all_frames: ColorAnalysisResult  # Averaged across all frames
    last_frame: ColorAnalysisResult

    # Metadata
    total_frames: int = 0
    frames_analyzed: int = 0
    fps: float = 0.0
    duration_seconds: float = 0.0

    # Changes detected (first vs last frame)
    colors_added: List[str] = field(default_factory=list)
    colors_removed: List[str] = field(default_factory=list)
    colors_increased: List[str] = field(default_factory=list)
    colors_decreased: List[str] = field(default_factory=list)

    # Summary
    change_summary: str = ""
    overall_shift: str = ""  # "warmer", "cooler", "more saturated"
```

## Use Cases

### 1. Quality Gating for VLM

Prevent hallucinations on blank frames:

```python
quality = compute_image_quality(image)
if not quality["is_usable"]:
    return {"error": f"Image quality too low: {quality['quality_description']}"}
```

### 2. Robot Motion Verification

Detect if trajectory was actually executed:

```python
motion = analyze_video_motion(trajectory_video)
if motion["stuck_detected"]:
    print("WARNING: Robot may not have moved during trajectory!")
```

### 3. Scene Composition Analysis

Understand color distribution:

```python
colors = analyze_image_colors(scene_capture)
print(f"Scene tone: {colors['dominant_hue']}")
print(f"Top color: {colors['colors'][0]['name']}")
```

### 4. Change Detection in Videos

Track color evolution:

```python
video_colors = analyze_video_colors(recording)
if video_colors["colors_added"]:
    print(f"New colors appeared: {video_colors['colors_added']}")
if "warmer" in video_colors["overall_shift"]:
    print("Scene became warmer over time")
```

## Performance Considerations

### Color Analysis

- **Quantization**: Reduces millions of colors to 125 bins
- **Sampling**: Video analyzes frames at 2 fps by default
- **Max frames**: Limited to 60 frames by default

### Motion Analysis

- **Gaussian blur**: (21, 21) kernel reduces noise
- **Threshold**: 25 pixel difference for motion detection
- **Sample rate**: 4 fps for balance of accuracy/speed

### Memory Usage

- Images: Loaded as numpy arrays, processed in-place
- Videos: Frames processed one at a time, not stored
- Results: Only aggregated statistics stored

## Troubleshooting

### Low Entropy Detection

If images consistently show low entropy:
- Check camera is pointed at scene
- Verify lighting in simulation
- Ensure timeline is playing

### Motion Not Detected

If motion analysis shows no movement:
- Verify trajectory was actually executed
- Check `motion_threshold` isn't too high
- Increase `sample_fps` for faster movements

### Color Names Unexpected

If color names seem wrong:
- Check HSV conversion is correct
- Verify modifiers match observed colors
- Consider adjusting saturation thresholds
