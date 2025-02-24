let sharedData = null;
let fetchPromise = null; // Store the fetch promise to avoid duplicate requests

async function fetchDataOnce() {
    if (!sharedData) {
        if (!fetchPromise) { // Only fetch if not already in progress
            fetchPromise = fetch("rendered/data.json")
                .then(response => {
                    if (!response.ok) throw new Error("Failed to fetch data");
                    return response.json();
                })
                .then(data => {
                    sharedData = data;
                    fetchPromise = null; // Reset fetchPromise after completion
                })
                .catch(error => {
                    console.error("Error loading JSON:", error);
                    fetchPromise = null; // Ensure future fetch attempts
                });
        }
        await fetchPromise; // Wait for the fetch to complete
    }
}


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