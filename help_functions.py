from geopy.geocoders import Nominatim

def generate_embed_code_from_address(address):
    geolocator = Nominatim(user_agent="map_embed_generator")
    location = geolocator.geocode(address)

    if location:
        latitude, longitude = location.latitude, location.longitude

        # Generisanje HTML embed koda za mapu sa OpenStreetMap-a
        embed_code = f'''
        <iframe width="600" height="450" frameborder="0" style="border:0"
            src="https://www.openstreetmap.org/export/embed.html?bbox={longitude-0.01}%2C{latitude-0.01}%2C{longitude+0.01}%2C{latitude+0.01}&layer=mapnik"
            allowfullscreen>
        </iframe>
        '''
        return embed_code
    else:
        return "Adresa nije pronađena."

# Unesi adresu za generisanje mape
user_address = input("Unesite adresu za generisanje mape na OpenStreetMap-u: ")

# Generisanje HTML embed koda na osnovu unete adrese
html_embed_from_address = generate_embed_code_from_address(user_address)
print(html_embed_from_address)
