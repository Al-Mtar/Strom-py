import Stromplaner  # noqa: F401
st.title("Mein projekt startet")

url = "https://api.open-meteo.com/v1/forecast"
params ={
    "latitude":52.52,
    "longitude": 13.41,
    "current" :"temperature_2m"
}
response= requests.get(url, params=params)
date = response.json()

st.write("Current Date:")
st.write(date["current"])
st.write(date)