"""
Random Video Source System - Usage Guide

Sistem ini menyediakan cara untuk mencari dan memilih video secara random
dari multiple providers (Pexels, Pixabay, Coverr).

## Fitur Utama

1. **Search & Select Random**: Cari video dari semua provider dan pilih 1 secara random
2. **Search & Select Multiple**: Cari video dan pilih beberapa secara random
3. **Provider Selection**: Pilih provider mana saja yang ingin digunakan
4. **Aspect Ratio Support**: Support portrait, landscape, dan square

## Instalasi

File yang ditambahkan:
- app/services/random_video_source.py - Core service untuk random selection
- app/controllers/v1/random_video.py - API endpoints
- Update app/router.py - Register router baru

## API Endpoints

### 1. Select Single Random Video

**Endpoint:** GET /api/v1/random-video/select

**Parameters:**
- search_term (required): Keyword untuk search
- min_duration (optional, default=5): Minimum durasi video dalam detik
- aspect (optional, default=portrait): Aspect ratio - portrait, landscape, atau square
- providers (optional): Comma-separated provider list (pexels,pixabay,coverr)

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/random-video/select?search_term=nature&min_duration=5&aspect=portrait"
```

**Response:**
```json
{
  "status": 200,
  "message": "success",
  "data": {
    "provider": "pexels",
    "url": "https://videos.pexels.com/video-preview.mp4",
    "duration": 10,
    "source_info": {
      "provider": "pexels",
      "search_term": "nature",
      "asset_id": "12345",
      "creator": {
        "name": "John Doe",
        "profile_page": "https://www.pexels.com/..."
      }
    }
  }
}
```

### 2. Select Multiple Random Videos

**Endpoint:** GET /api/v1/random-video/select-multiple

**Parameters:**
- search_term (required): Keyword untuk search
- count (optional, default=5): Jumlah video yang ingin dipilih (1-50)
- min_duration (optional, default=5): Minimum durasi video dalam detik
- aspect (optional, default=portrait): Aspect ratio
- providers (optional): Comma-separated provider list

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/random-video/select-multiple?search_term=mountain&count=3&aspect=landscape&providers=pexels,pixabay"
```

**Response:**
```json
{
  "status": 200,
  "message": "success",
  "data": {
    "total": 3,
    "videos": [
      {
        "provider": "pexels",
        "url": "https://videos.pexels.com/video1.mp4",
        "duration": 8,
        "source_info": {...}
      },
      {
        "provider": "pixabay",
        "url": "https://videos.pixabay.com/video2.mp4",
        "duration": 12,
        "source_info": {...}
      },
      {
        "provider": "coverr",
        "url": "https://videos.coverr.co/video3.mp4",
        "duration": 10,
        "source_info": {...}
      }
    ]
  }
}
```

## Usage dalam Code

### 1. Menggunakan Convenience Functions

```python
from app.services.random_video_source import search_and_select_random
from app.models.schema import VideoAspect

# Select single random video
video = search_and_select_random(
    search_term="beach",
    minimum_duration=5,
    video_aspect=VideoAspect.portrait,
    enabled_providers=["pexels", "pixabay"]  # Optional
)

if video:
    print(f"Selected: {video.provider} - {video.url}")
```

### 2. Menggunakan Class

```python
from app.services.random_video_source import RandomVideoSelector
from app.models.schema import VideoAspect

selector = RandomVideoSelector()

# Search dan select random
video = selector.select_random(
    search_term="city",
    minimum_duration=5,
    video_aspect=VideoAspect.landscape,
    enabled_providers=["pexels", "pixabay", "coverr"]
)

# Search dan select multiple
videos = selector.select_multiple_random(
    search_term="nature",
    count=5,
    minimum_duration=5,
    video_aspect=VideoAspect.portrait
)

# Atau hanya search tanpa selection
all_videos = selector.search_from_all_sources(
    search_term="mountain",
    minimum_duration=5,
    video_aspect=VideoAspect.landscape
)

# Random select dari hasil
import random
selected = random.choice(all_videos) if all_videos else None
```

## Requirements

Sistem ini memerlukan:
1. Valid API keys untuk provider yang ingin digunakan di config.toml:
   - pexels_api_keys
   - pixabay_api_keys
   - coverr_api_keys

2. Dependencies yang sudah ada di project:
   - requests
   - loguru
   - FastAPI
   - Pydantic

## Error Handling

Sistem akan return:
- 404 jika tidak ada video yang ditemukan
- 400 jika parameter invalid (aspect, provider, dll)
- 500 jika ada error saat mencari/select

Semua error dari individual provider akan di-log tapi tidak menghentikan search dari provider lain.

## Performance Notes

1. Search dilakukan secara sequential ke setiap provider
2. Jika satu provider gagal, sistem melanjutkan ke provider lain
3. Random selection dari total hasil dari semua provider
4. Minimum durasi, aspect ratio filtering dilakukan di level provider

## Konfigurasi (Optional)

Di config.toml:
```toml
# Enable/disable providers
pexels_api_keys = "your-key"
pixabay_api_keys = "your-key"
coverr_api_keys = "your-key"

# TLS verification (jika perlu)
tls_verify = true
```

## Contoh Real-World Usage

```python
from app.services.random_video_source import search_and_select_multiple
from app.models.schema import VideoAspect

def create_video_with_random_materials(topic: str, video_count: int = 5):
    '''Generate video menggunakan random materials dari multiple providers'''
    
    videos = search_and_select_multiple(
        search_term=topic,
        count=video_count,
        minimum_duration=5,
        video_aspect=VideoAspect.portrait,
        enabled_providers=["pexels", "pixabay", "coverr"]
    )
    
    if not videos:
        raise Exception(f"No videos found for topic: {topic}")
    
    # Gunakan untuk membuat video
    material_list = [v.url for v in videos]
    return material_list
```

## Troubleshooting

**Problem: No videos found**
- Cek API keys di config.toml
- Cek koneksi internet dan proxy setting
- Coba dengan search term yang berbeda
- Cek logs untuk error dari masing-masing provider

**Problem: All requests failed**
- Verify API keys validity
- Check network connectivity
- Review proxy configuration
- Check Cloudflare blocks (untuk Pixabay)

**Problem: Same videos repeatedly selected**
- Ini normal karena random selection
- Jika perlu unique videos, gunakan select_multiple_random dengan count > 1
- Atau simpan selected video IDs dan exclude dari next selection
