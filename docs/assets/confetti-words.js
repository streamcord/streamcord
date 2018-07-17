for (var i = 0; i < 40; i++) {
  create(i);
}

function create(i) {
  var height = Math.random() * 8;
  var words = ["Hello", "Hola", "Bonjour", "Salut", "Hallo", "Ciao", "Merhaba", "cześć", "Olá", "xin chào", "你好", "こんにちは", "여보세요", "مرحبا", "Здравствуйте", "Χαίρετε", "नमस्ते"];
  var word = words[Math.floor(Math.random()*words.length)];
  $('<div class="confetti-'+i+'">'+word+'</div>').css({
    "height" : height+"px",
    "top" : -Math.random()*20+"%",
    "left" : Math.random()*100+"%",
    "opacity" : Math.random() / 2 + 0.1,
    "transform" : "rotate("+Math.random()*360+"deg)"
  }).appendTo('.wrapper');

  drop(i);
}

function drop(x) {
  $('.confetti-'+x).animate({
    top: "100%",
    left: "+="+Math.random()*15+"%"
  }, Math.random()*3000 + 3000, function() {
    reset(x);
  });
}

function reset(x) {
  $('.confetti-'+x).animate({
    "top" : -Math.random()*20+"%",
    "left" : "-="+Math.random()*5+"%"
  }, 0, function() {
    drop(x);
  });
}
