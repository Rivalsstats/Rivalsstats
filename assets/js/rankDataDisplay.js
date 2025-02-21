async function processData() {
    await fetchDataOnce();
    if (sharedData) {
        document.getElementById("ranked_players").textContent = sharedData.total_ranked_players[0].total;
            document.getElementById("total_players").textContent = sharedData.total_players[0].total;
            document.getElementById("rank_img").src = sharedData.rank_image;
            document.getElementById("rank_img").alt = sharedData.average_rank_including_name + " Image";
            document.getElementById("rank_name").textContent = sharedData.average_rank_including_name;
            document.getElementById("rank_points").textContent = sharedData.average_rank_including_points;
            document.getElementById("rank_img_ex").src = sharedData.rank_image_ex;
            document.getElementById("rank_img_ex").alt = sharedData.average_rank_excluding_name + " Image";
            document.getElementById("rank_name_ex").textContent = sharedData.average_rank_excluding_name;
            document.getElementById("rank_points_ex").textContent = sharedData.average_rank_excluding_points;
    } else {
        console.log("Data is not yet available.");
    }
}

// Make sure to call fetchDataOnce before processing
processData();