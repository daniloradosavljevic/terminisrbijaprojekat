// Učitavanje JSON fajla
fetch('gradovi.json')
  .then(response => response.json())
  .then(data => {
    // Poziv funkcije za kreiranje selekt polja
    createCitySelect(data);
  })
  .catch(error => {
    console.log('Došlo je do greške pri učitavanju fajla:', error);
  });

// Funkcija za kreiranje selekt polja sa gradovima
function createCitySelect(cities) {
  const selectElement = document.createElement('select');
  selectElement.setAttribute('id', 'citySelect');

  // Dodavanje opcija za svaki grad
  cities.forEach(city => {
    const option = document.createElement('option');
    option.value = city.city;
    option.textContent = city.city;
    selectElement.appendChild(option);
  });

  // Dodavanje selekt polja na željeni deo HTML-a
  const container = document.getElementById('cityContainer');
  container.appendChild(selectElement);
}
