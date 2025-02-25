function timeSinceRender(renderTime) {
    const now = new Date();
    
    // Adjust renderTime to the correct timezone
    const renderDate = new Date(renderTime);
    const diffMs = now - renderDate;
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    let message = "";
    if (diffMinutes < 2) {
      message = "Last update: " + diffMinutes + " minute ago";
    } else
    if (diffMinutes < 60) {
      message = "Last update: " + diffMinutes + " minutes ago";
    } else if (diffHours < 2) {
      message = "Last update: " + diffHours + " hour ago";
    } else if (diffHours < 24) {
      message = "Last update: " + diffHours + " hours ago";
    } else if (diffHours < 48) {
      message = "Last update: " + diffHours + " day ago";
    } else {
      message = "Last update: " + diffDays + " days ago";
    }

    document.getElementById("last-rendered").innerText = message;
}


async function processData() {
    await fetchDataOnce();
    if (sharedData) {
        // Use the shared data here
        timeSinceRender(sharedData.latest_render);
        // Call the relevant function that needs the data
    } else {
        console.log("Data is not yet available.");
    }
}

// Make sure to call fetchDataOnce before processing
processData();