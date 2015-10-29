$(document).ready(function() { 
    h = Math.max($(".two-thirds-column").height(), $(".one-third-column").height());
    $(".two-thirds-column").height(h);
    $(".one-third-column").height(h);
});
