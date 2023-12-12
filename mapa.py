from geopy.geocoders import Nominatim


def generate_embed_code_from_address(address):
    geolocator = Nominatim(user_agent="map_embed_generator")
    location = geolocator.geocode(address)

    if location:
        latitude, longitude = location.latitude, location.longitude

        # Preciznije određivanje granica za zumiranje
        zoom_level = 18  # Nivo zumiranja
        delta = 0.005  # Delta za preciznije zumiranje

        # Generisanje HTML embed koda za mapu sa OpenStreetMap-a
        embed_code = f"""
        <iframe width="600" height="450" frameborder="0" style="border:0"
            src="https://www.openstreetmap.org/export/embed.html?bbox={longitude-delta}%2C{latitude-delta}%2C{longitude+delta}%2C{latitude+delta}&layer=mapnik&marker={latitude}%2C{longitude}"
            allowfullscreen>
        </iframe>
        """
        return embed_code
    else:
        return "Adresa nije pronađena."


# Unesi adresu za generisanje mape
user_address = input("Unesite adresu za generisanje mape na OpenStreetMap-u: ")

# Generisanje HTML embed koda na osnovu unete adrese
html_embed_from_address = generate_embed_code_from_address(user_address)
print(html_embed_from_address)
