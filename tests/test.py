import httpx
import asyncio

FIREBASE_URL = 'https://last-197cd-default-rtdb.firebaseio.com/routines.json'


#function to fetch ct data from firebase url
async def get_ct_data():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(FIREBASE_URL)
            response.raise_for_status()
            print(response.json())
            return response.json() or {}
    except Exception as e:
        print(f"Error in get_ct_data functio. \n\n Error Code -{e}")
        return None
    
asyncio.run(get_ct_data())