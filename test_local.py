import asyncio
from api.main import generate_music, GenerateRequest, load_ai_assets

load_ai_assets()

async def test():
    req = GenerateRequest(mood="happy", creativity=0.8, tempo=120, duration=30)
    try:
        res = await generate_music(req)
        print("SUCCESS:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
