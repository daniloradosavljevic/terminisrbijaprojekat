from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

def generate_embed_code_from_address(address):
    try:
        geolocator = Nominatim(user_agent="map_embed_generator")
        location = geolocator.geocode(address)

        if location:
            latitude, longitude = location.latitude, location.longitude

            zoom_level = 18  
            delta = 0.005  # ovo sluzi za preciznije zumiranje

            embed_code = f"""
            <iframe width="600" height="450" frameborder="0" style="border:0"
                src="https://www.openstreetmap.org/export/embed.html?bbox={longitude-delta}%2C{latitude-delta}%2C{longitude+delta}%2C{latitude+delta}&layer=mapnik&marker={latitude}%2C{longitude}"
                allowfullscreen>
            </iframe>
            """
            return embed_code
        else:
            return "Za datu adresu nije moguće pronaći lokaciju na mapi"
    except GeocoderTimedOut as e:
        return "Mapa trenutno nije dostupna."
