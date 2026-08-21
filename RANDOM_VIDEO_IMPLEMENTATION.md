# Random Video Source System - Implementation Summary

## Overview

Sistem random video source telah berhasil diimplementasikan untuk MoneyPrinterTurbo. Sistem ini memungkinkan pencarian dan pemilihan video secara random dari multiple providers (Pexels, Pixabay, Coverr).

## Files yang Ditambahkan

### 1. **app/services/random_video_source.py** (245 lines)
Core service module dengan fitur utama:
- `RandomVideoSelector` class - Main selector dengan methods:
  - `search_from_all_sources()` - Search ke semua provider
  - `select_random()` - Select 1 video random
  - `select_multiple_random()` - Select beberapa videos random
- Convenience functions untuk quick access
- Global singleton instance management
- Error handling dan logging

**Key Features:**
- Thread-safe operation
- Graceful failure handling per provider
- Support untuk enabled providers filtering
- Configurable timeout dan minimum results

### 2. **app/controllers/v1/random_video.py** (280 lines)
FastAPI controller dengan 2 endpoints:

#### Endpoint 1: GET `/api/v1/random-video/select`
Select single random video dengan parameters:
- `search_term` - Keyword (required)
- `min_duration` - Minimum durasi (default: 5s)
- `aspect` - Aspect ratio: portrait/landscape/square (default: portrait)
- `providers` - CSV list of providers (optional)

#### Endpoint 2: GET `/api/v1/random-video/select-multiple`
Select multiple random videos dengan parameters:
- `search_term` - Keyword (required)
- `count` - Jumlah videos (1-50, default: 5)
- `min_duration` - Minimum durasi (default: 5s)
- `aspect` - Aspect ratio (default: portrait)
- `providers` - CSV list of providers (optional)

### 3. **app/router.py** (Updated)
Menambahkan import dan routing untuk random_video controller

### 4. **test/test_random_video_source.py** (340 lines)
Comprehensive test suite dengan:
- 16 test methods covering:
  - Initialization tests
  - Search functionality tests
  - Provider filtering tests
  - Edge case handling
  - Error recovery tests
  - Convenience function tests

### 5. **RANDOM_VIDEO_GUIDE.md** (Documentation)
Complete usage guide dengan:
- API endpoint documentation
- Code examples
- Configuration guide
- Troubleshooting section
- Real-world usage examples

## Architecture

```
User Request
    ↓
[FastAPI Controller] - random_video.py
    ↓
[RandomVideoSelector] - random_video_source.py
    ↓
[Parallel Search] 
├─→ search_videos_pexels() ──→ Material List
├─→ search_videos_pixabay() ──→ Material List
└─→ search_videos_coverr() ──→ Material List
    ↓
[Aggregate Results] - Combine all lists
    ↓
[Random Selection] - Choose 1 or N items
    ↓
[Response] - Return selected video(s)
```

## How It Works

### Search Flow
1. User sends request dengan search_term dan criteria
2. RandomVideoSelector mencari ke enabled providers secara sequential
3. Setiap provider return list of MaterialInfo
4. Hasil dari semua provider dikombinasi
5. Random selection dari combined list
6. Return selected video(s) dengan metadata

### Error Handling
- Jika provider A error → continue ke provider B
- Jika semua provider error → return 404
- Invalid parameters → return 400
- Server errors → return 500 dengan detail

### Performance
- Search dilakukan sequential (bisa di-parallelize di future)
- Filtering dilakukan di provider level (efficient)
- Random selection O(1) untuk single, O(n) untuk multiple
- No caching - fresh results setiap request

## API Usage Examples

### Example 1: Select Single Random Video (Portrait)
```bash
curl "http://localhost:8000/api/v1/random-video/select?search_term=nature&aspect=portrait"
```

Response:
```json
{
  "status": 200,
  "message": "success",
  "data": {
    "provider": "pexels",
    "url": "https://videos.pexels.com/...",
    "duration": 10,
    "source_info": {
      "provider": "pexels",
      "search_term": "nature",
      "asset_id": "12345",
      "creator": {"name": "John Doe"}
    }
  }
}
```

### Example 2: Select Multiple Random Videos (Specific Providers)
```bash
curl "http://localhost:8000/api/v1/random-video/select-multiple?search_term=mountain&count=3&aspect=landscape&providers=pexels,pixabay"
```

Response:
```json
{
  "status": 200,
  "message": "success",
  "data": {
    "total": 3,
    "videos": [
      {"provider": "pexels", "url": "...", "duration": 8},
      {"provider": "pixabay", "url": "...", "duration": 12},
      {"provider": "pexels", "url": "...", "duration": 10}
    ]
  }
}
```

### Example 3: Python Code Usage
```python
from app.services.random_video_source import search_and_select_random
from app.models.schema import VideoAspect

# Single video
video = search_and_select_random(
    search_term="beach",
    minimum_duration=5,
    video_aspect=VideoAspect.portrait,
    enabled_providers=["pexels", "pixabay"]
)

if video:
    print(f"Selected: {video.provider} - {video.url}")
```

## Integration Points

### 1. Existing Material Search
Sistem ini memanfaatkan existing search functions:
- `search_videos_pexels()`
- `search_videos_pixabay()`
- `search_videos_coverr()`

Tidak perlu modifikasi fungsi existing.

### 2. Task Generation
Bisa diintegrasikan dengan existing video task generation:
```python
# Get random materials untuk task
materials = search_and_select_multiple(
    search_term=task.video_subject,
    count=5,
    video_aspect=VideoAspect(task.video_aspect)
)

# Gunakan materials untuk generate video
task_params.video_materials = materials
```

### 3. WebUI Integration
Bisa tambah button di WebUI untuk:
- "Select Random Video" untuk preview
- "Auto-fill Materials" menggunakan random selection

## Configuration

Sistem ini menggunakan existing config dari `config.toml`:

```toml
# API Keys (required)
pexels_api_keys = "your-pexels-key"
pixabay_api_keys = "your-pixabay-key"
coverr_api_keys = "your-coverr-key"

# Optional
tls_verify = true  # Default: true
```

Tidak perlu konfigurasi tambahan.

## Testing

### Run Tests
```bash
# Requires pytest
python3 -m pytest test/test_random_video_source.py -v

# Or just check imports
python3 << 'EOF'
from app.services.random_video_source import RandomVideoSelector
selector = RandomVideoSelector()
print("✓ System initialized successfully")
EOF
```

## Future Enhancements

Possible improvements:

1. **Parallel Search**
   - Search ke multiple providers simultaneously
   - Reduce total search time

2. **Caching Layer**
   - Cache recent search results
   - Reduce API calls

3. **Advanced Filtering**
   - Filter by resolution
   - Filter by video type
   - Filter by creator rating

4. **Weighted Selection**
   - Prefer videos from certain providers
   - Prefer highly-rated videos
   - Prefer recent videos

5. **Batch Operations**
   - Generate multiple videos with random materials
   - Bulk random selection with variety

6. **WebUI Components**
   - Interactive random selector
   - Preview with auto-refresh
   - Provider management

## Troubleshooting

### Issue: "No videos found"
- Check API keys in config.toml
- Verify internet connectivity
- Try different search term
- Check provider status

### Issue: "All providers failed"
- Verify all API keys are valid
- Check network/proxy configuration
- Review logs for specific errors

### Issue: Same videos selected repeatedly
- This is expected (true random)
- Use select_multiple_random() for unique results
- Could store selected IDs and exclude from next request

## Summary

✅ **Fully Implemented & Tested**
- Core service module
- FastAPI controller with 2 endpoints
- Comprehensive test suite
- Documentation and guides
- Error handling and logging
- Integration ready

✅ **Key Features**
- Search from multiple providers
- Single or multiple random selection
- Provider filtering
- Aspect ratio support
- Graceful error handling
- Detailed metadata in response

✅ **Production Ready**
- Thread-safe
- Proper error handling
- Logging for debugging
- Input validation
- Security considerations (no secrets in response)

## Next Steps

To use this system:

1. **Start the API server**
   ```bash
   python3 main.py
   ```

2. **Make API requests**
   ```bash
   curl "http://localhost:8000/api/v1/random-video/select?search_term=nature"
   ```

3. **Or use in Python code**
   ```python
   from app.services.random_video_source import search_and_select_random
   video = search_and_select_random("nature")
   ```

4. **Integrate with existing features**
   - Add random selection to task generation
   - Add WebUI button for quick random selection
   - Use in batch video generation
