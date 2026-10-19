/* Mejoras de interfaz (solo visuales, no tocan la lógica de la app) */
(function(){
  // Cierra el menú desplegable al tocar fuera o al presionar Escape
  document.addEventListener('click', function(e){
    document.querySelectorAll('details.menu[open]').forEach(function(d){
      if(!d.contains(e.target)) d.removeAttribute('open');
    });
  });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape'){
      document.querySelectorAll('details.menu[open]').forEach(function(d){ d.removeAttribute('open'); });
    }
  });

  // Muestra el nombre del archivo elegido en los selectores de archivo
  document.querySelectorAll('label.file input[type=file]').forEach(function(input){
    var label = input.closest('label.file');
    var text = label.querySelector('.file-label');
    if(!text) return;
    var original = text.textContent;
    input.addEventListener('change', function(){
      var n = input.files ? input.files.length : 0;
      if(n === 0){ text.textContent = original; label.classList.remove('has-file'); return; }
      text.textContent = n === 1 ? input.files[0].name : n + ' archivos seleccionados';
      label.classList.add('has-file');
    });
  });
})();
