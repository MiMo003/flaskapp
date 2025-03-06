// Obtener los elementos del modal y los botones
const openModalBtn = document.getElementById('openModalBtn');
const sideModal = document.getElementById('sideModal');
const closeModalBtn = document.getElementById('closeModalBtn');

// Obtener todos los botones con imágenes
const buttons = document.querySelectorAll('.muestraH button');
const selectedImage = document.getElementById('selectedImage'); // Elemento donde se muestra la imagen seleccionada

let quantity = 0;

var modal = document.getElementById('myModal');

// Función para abrir el modal
openModalBtn.addEventListener('click', () => {
  sideModal.classList.add('open'); // Añadir la clase 'open' para que el modal se deslice
});

// Función para cerrar el modal
closeModalBtn.addEventListener('click', () => {
  sideModal.classList.remove('open'); // Eliminar la clase 'open' para ocultar el modal
});

// También se puede cerrar el modal si se hace clic fuera de él
window.addEventListener('click', (e) => {
  if (e.target === sideModal) {
    sideModal.classList.remove('open'); // Eliminar la clase 'open' al hacer clic fuera
  }
});

// Cuando se hace clic fuera del contenido del modal, el modal se cierra
window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = "none";
    }
}

function increaseQuantity(parametro) {
    parametro++;
    document.getElementById(parametro).innerText = parametro;
}

function decreaseQuantity(parametro) {
    if (parametro > 0) {
        parametro--;
        document.getElementById("quantity").innerText = quantity;
    }
}

buttons.forEach(button => {
    button.addEventListener('click', () => {
        // Obtener la fuente de la imagen seleccionada
        const imageSrc = button.querySelector('img').src;
        // Cambiar la imagen mostrada
        selectedImage.src = imageSrc;

        // Remover la clase 'selected' de todos los botones
        buttons.forEach(b => b.classList.remove('selected'));
        // Agregar la clase 'selected' al botón clickeado
        button.classList.add('selected');
    });
});
