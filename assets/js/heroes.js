
// Initialize all tooltips
var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
return new bootstrap.Tooltip(tooltipTriggerEl)
})
// List sort/search options
var options = {
    valueNames: [ 'card-title', { name: 'role', attr: 'alt' }, 'overall-winrate', 'overall-pickrate', 'attack-type' ]
  };
var heroList = new List('heros-list-container', options);


function initMarquee($container) {
    $container.find('.hero-carousel-track').each(function () {
        var $track = $(this);
        // Destroy any existing marquee instance
        $track.marquee('destroy');
        
        // Initialize marquee
        $track.marquee({
        duration: 30000,  // Adjust speed (lower = faster, higher = slower)
        gap: 20,          // Adjust gap as needed
        delayBeforeStart: 0,
        direction: 'left',
        duplicated: true, // Enables seamless looping
        startVisible: true
        });
    });
}

$(document).ready(function () {
// Initialize marquee for items outside modals
initMarquee($(document));

// Also initialize for items inside modals when they're shown
$('.modal').on('shown.bs.modal', function () {
    initMarquee($(this));
});
});