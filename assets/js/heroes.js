
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
document.querySelectorAll("#copy-btn").forEach((button) => {
    console.log("adding event listeners")
    button.addEventListener("click", function () {
        console.log("clicked")
      const parentDiv = this.closest(".details"); // Find closest parent match-header
      const replayId = parentDiv.querySelector("#replay-id").textContent; // Select replay ID inside same match-header
        
      navigator.clipboard.writeText(replayId).then(() => {
        this.textContent = "Copied!";
        setTimeout(() => (this.textContent = "Copy"), 1500); // Reset text after 1.5s
      });
    });
  });

// Also initialize for items inside modals when they're shown
$('.modal').on('shown.bs.modal', function () {
    initMarquee($(this));
});
});
