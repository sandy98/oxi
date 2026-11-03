let menuitems;
document.addEventListener("DOMContentLoaded", function() {
    // Your code here
    menuitems = document.querySelectorAll("menu-item");
    menuitems.forEach(mi => mi.toggleAttribute("use-default-handler", true));
//    document.querySelector('nav').style.display = 'inherit';
    console.log("The DOM has fully loaded.");
});
