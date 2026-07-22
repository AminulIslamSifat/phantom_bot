

def call_api():
    

    return response


response = call_api()

with open("routine.jpg", "wb") as f:
    f.write(response.read())