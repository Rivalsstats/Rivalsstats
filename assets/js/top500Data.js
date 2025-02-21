async function processData() {
    await fetchDataOnce();
    if (sharedData) {
        // Use the shared data here
        document.getElementById("unique_matches").textContent = sharedData.unique_matches;
        document.getElementById("unique_players").textContent = sharedData.unique_players;
    } else {
        console.log("Data is not yet available.");
    }
}

// Make sure to call fetchDataOnce before processing
processData();