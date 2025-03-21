// Global variables to hold our minimal index and hero definitions.
let indexData = null;  // Expected structure: { matches: { match_uid: { … } }, heroes: { hero_id: [match_uid, ...] } }
let heroData = null;   // Array of hero definitions from all_heroes.json
let heroesIndex = null; // Expected structure: { hero_id: { synergies: [ [hero_id, hero_id], … ], counters: [ [hero_id, hero_id], … ] } }

let selectedHeroes = {
  teamHeroes: [],
  opposingHero: []
};
// Load hero definitions.
fetch('/data/latest/heroes/all_heroes.json')
  .then(response => response.json())
  .then(data => { heroData = data; populateHeroDropdown(data); })
  .catch(error => console.error('Error loading hero data:', error));

// Load the minimal index containing filtering facets for all matches.
fetch('/data/index.json')
  .then(response => response.json())
  .then(data => {
    indexData = data;
    // Render all matches (using the minimal filtering facets).
    renderMatches(Object.values(indexData));
  })
  .catch(error => console.error('Error loading index:', error));
//load map index
  fetch('/data/map_index.json')
  .then(response => response.json())
  .then(data => { mapIndex = data; })
  .catch(error => console.error('Error loading map index:', error));
// load map info
  fetch('/data/latest/latest_maps.json')
  .then(response => response.json())
  .then(data => {
    mapData = data;
    populateMapDropdown(data);
  })
  .catch(error => console.error('Error loading map data:', error));

// Format a timestamp into a local time string.
function formatTimestamp(timestamp) {
  const d = new Date(timestamp * 1000);
  return d.toLocaleString();
}

function populateMapDropdown(maps) {
    const mapFilter = document.getElementById("mapFilter");
    mapFilter.innerHTML = ''; // Clear existing options

    const uniqueMaps = {};
    maps.forEach(map => {
        if (uniqueMaps[map.name]) {
          uniqueMaps[map.name].push(map.id);
        } else {
          uniqueMaps[map.name] = [map.id];
        }
    });

    Object.keys(uniqueMaps).forEach(mapName => {
        const option = document.createElement("option");
        option.value = uniqueMaps[mapName].join(","); // e.g., "101,205" if these IDs share the same name
        option.textContent = mapName;
        mapFilter.appendChild(option);
      });
      $('#mapFilter').selectpicker('refresh');
  }

function populateHeroDropdown(heroData){
  // Populate the select with hero options
  const teamHeroes = document.getElementById("teamHeroes");
  const opponentHeroes = document.getElementById("opposingHeroes");
  heroData.forEach(hero => {
    const option = document.createElement("option");
    option.value = hero.id;
    option.text = hero.name;
    teamHeroes.appendChild(option);
    const optionOpponent = option.cloneNode(true); // Clone the option
    opponentHeroes.appendChild(optionOpponent);
  });
  $('#teamHeroes').selectpicker('refresh');
  $('#opposingHeroes').selectpicker('refresh');
}  
document.getElementById("mapFilter").addEventListener("change", filterHeroes);
document.getElementById("sortMatches").addEventListener("change", filterHeroes);
document.querySelectorAll('input[name="sortOrder"]').forEach((radio) => {
  radio.addEventListener("change", () => {filterHeroes()});
});
function selectHero(inputField, heroName, heroId) {
    const fieldId = inputField.id;
    // Prevent duplicate selection.
    if (selectedHeroes[fieldId].some(h => h.id === heroId)) return;
    selectedHeroes[fieldId].push({ name: heroName, id: heroId });
    // Find the dedicated container for selected heroes within the multi-select container.
    const container = inputField.parentElement; // .multi-select-container
    const tagsContainer = container.querySelector('.selected-heroes');
    
    // Create the tag element.
    const selectedSpan = document.createElement("span");
    selectedSpan.classList.add("selected-hero");
    selectedSpan.textContent = heroName;
    
    // Create the remove button.
    const removeBtn = document.createElement("span");
    removeBtn.classList.add("remove-hero");
    removeBtn.textContent = " ×";
    removeBtn.addEventListener("click", () => {
      tagsContainer.removeChild(selectedSpan);
      selectedHeroes[fieldId] = selectedHeroes[fieldId].filter(h => h.id !== heroId);
      filterHeroes();
    });
    
    // Append remove button to the tag, then add the tag to the container.
    selectedSpan.appendChild(removeBtn);
    tagsContainer.appendChild(selectedSpan);
    
    // Clear the input field.
    inputField.value = "";
    filterHeroes();
  }
  

function getSelectedHeroIds(fieldId) {
  return selectedHeroes[fieldId].map(hero => hero.id);
}

$('#teamHeroes').on('changed.bs.select', function (e, clickedIndex, isSelected, previousValue) {
  // Get all selected hero IDs from the bootstrap-select
  const selectedOptions = $(this).val() || [];
  selectedHeroes.teamHeroes = selectedOptions.map(heroId => {
    // Find the hero object from heroData
    const hero = heroData.find(h => h.id === heroId);
    return { id: heroId, name: hero ? hero.name : '' };
  });
  filterHeroes();
});

$('#opposingHeroes').on('changed.bs.select', function (e, clickedIndex, isSelected, previousValue) {
  // Get all selected hero IDs from the bootstrap-select
  const selectedOptions = $(this).val() || [];
  selectedHeroes.opposingHero = selectedOptions.map(heroId => {
    // Find the hero object from heroData
    const hero = heroData.find(h => h.id === heroId);
    return { id: heroId, name: hero ? hero.name : '' };
  });
  filterHeroes();
});



// Format duration (in seconds) into hh:mm:ss or mm:ss.
function formatDuration(seconds) {
  seconds = Math.floor(seconds);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  let formatted = "";
  if (h > 0) {
    formatted += h + ":" + (m < 10 ? "0" : "") + m + ":";
  } else {
    formatted += m + ":";
  }
  formatted += (s < 10 ? "0" : "") + s;
  return formatted;
}

// Render matches into the accordion.
function renderMatches(matches) {
  const accordion = document.getElementById("matchesAccordion");
  accordion.innerHTML = "";

  if (matches.length === 0) {
    accordion.innerHTML = "<p>No matches found with the specified criteria.</p>";
    return;
  }

  const sortBy = document.getElementById("sortMatches").value;
  const sortOrder = document.querySelector('input[name="sortOrder"]:checked').value;
  if (sortBy === "timestamp") {
    matches.sort((a, b) => sortOrder === 'asc'
      ? a.match_timestamp - b.match_timestamp
      : b.match_timestamp - a.match_timestamp);
  } else if (sortBy === "duration") {
    matches.sort((a, b) => sortOrder === 'asc'
      ? a.duration - b.duration
      : b.duration - a.duration);
  } else if (sortBy === "map") {
    matches.sort((a, b) => {
      const cmp = a.map.toUpperCase().localeCompare(b.map.toUpperCase());
      return sortOrder === 'asc' ? cmp : -cmp;
    });
  }

  matches.forEach(match => {
    const headingId = "heading_" + match.match_uid;
    const collapseId = "collapse_" + match.match_uid;
    const season = match.season || "N/A";
    const gamemode = match.game_mode ? match.game_mode : match.gamemode || "N/A";
    const map = match.map || "N/A";
    const duration = match.duration ? formatDuration(match.duration) : "N/A";
    const timestampFormatted = formatTimestamp(match.match_timestamp);

    const item = document.createElement("div");
    item.className = "accordion-item";
    item.innerHTML = `
      <h2 class="accordion-header" id="${headingId}">
        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse"
          data-bs-target="#${collapseId}" aria-expanded="false" aria-controls="${collapseId}">
          <div class="match-summary">
            <div class="summary-top">
              <div><strong>Season:</strong> ${season}</div>
              <div>${map}</div>
              <div>${duration}</div>
              <div>${gamemode}</div>
              <div>${timestampFormatted}</div>
            </div>
          </div>
        </button>
      </h2>
      <div id="${collapseId}" class="accordion-collapse collapse" aria-labelledby="${headingId}" >
        <div class="accordion-body">
          <p>Loading match details...</p>
        </div>
      </div>
    `;
    accordion.appendChild(item);

    // Lazy-load full match details when this item is expanded.
    const collapseElement = document.getElementById(collapseId);
    collapseElement.addEventListener('shown.bs.collapse', function () {
      const body = collapseElement.querySelector('.accordion-body');
      if (body.getAttribute('data-loaded') !== 'true') {
        fetchFullMatchDetails(match, body);
        bodyElement.closest(".accordion-item").scrollIntoView({
            behavior: "smooth",
            block: "start"
          });
      }
    });
  });
}
const medalMapping = {
  "Triple!": "3Kill.png",
  "Quad!": "4Kill.png",
  "Penta!": "5Kill.png",
  "Hexa!": "6Kill.png",
  "Trusty Sidekick": "assists.png",
  "Impentrable Defence": "blocked.png",
  "Relentless Offense": "damage.png",
  "Gifted Healer": "healing.png",
  "Mighty Vanquisher": "kills.png"
};
const multiKillOrder = {
  "Triple!": 1,
  "Quad!": 2,
  "Penta!": 3,
  "Hexa!": 4
};
// Helper function to generate medal icon HTML from a badges array.
function generateMedals(badges) {
  if (!badges || badges.length === 0) {
    return "—";
  }

      // Find the highest multi-kill badge if present.
  let highestMultiKill = null;
  badges.forEach(badge => {
    if (multiKillOrder[badge.name]) {
      if (
        !highestMultiKill ||
        multiKillOrder[badge.name] > multiKillOrder[highestMultiKill.name]
      ) {
        highestMultiKill = badge;
      }
    }
  });

  // Filter out all multi-kill badges.
  let filteredBadges = badges.filter(badge => !multiKillOrder[badge.name]);

  // If a multi-kill badge was found, add the highest one.
  if (highestMultiKill) {
    filteredBadges.push(highestMultiKill);
  }
  
  return filteredBadges.map(badge => {
    const fileName = medalMapping[badge.name];
    if (fileName) {
      return `<img class="medal-icon" src="icons/medals/${fileName}" alt="${badge.name}">`;
    }
    // Fallback behavior in case a badge doesn't match the mapping.
    if (badge.name !== "MVP" && badge.name !== "SVP") {
      console.warn('Unrecognized badge:', badge.name);
    }
    return "";
  }).join('');
}

function getHeroIcon(heroID) {
  const hero = heroData.find((hero) => hero.id == heroID.toString());
  return hero ? `icons/hero_icons/${hero.name.replace(/ /g, "_")}.png` : "";
}

function getRole(heroID) {
  const hero = heroData.find((hero) => hero.id == heroID.toString());
  return hero ? hero.role.toLowerCase() : "";
}

function getRoleIcon(heroID) {
  const role = getRole(heroID);
  return role ? `icons/role_icons/${role}.png` : "";
}


const roleOrder = {
  "vanguard": 1,
  "duelist": 2,
  "strategist": 3
};
function generatePlayerHeroRows(players, matchDetails) {
  // Build groups: one per player.
  const groups = players.map(player => {
    // Assume player.player_heroes exists and each hero has a "play_time" and a "role" property.
    if (!player.heroes || player.heroes.length === 0) {
      return { player, mainHero: null, altHeroes: [] };
    }
    // Find the hero with maximum play_time.
    const mainHero = player.heroes.reduce((prev, curr) =>
      curr.play_time > prev.play_time ? curr : prev
    );
    // Alt heroes are all hero entries except the main one.
    const altHeroes = player.heroes.filter(hero => hero !== mainHero);
    // Sort alt heroes by role order.
    altHeroes.sort((a, b) => {
      const aRole = getRole(a.hero_id) ? getRole(a.hero_id) : "";
      const bRole = getRole(b.hero_id) ? getRole(b.hero_id) : "";
      return (roleOrder[aRole] || 99) - (roleOrder[bRole] || 99);
    });
    return { player, mainHero, altHeroes };
  });

  // Sort groups by the main hero's role (using our custom order).
  groups.sort((a, b) => {
    const aRole = a.mainHero && getRole(a.mainHero.hero_id) ? getRole(a.mainHero.hero_id) : "";
    const bRole = b.mainHero && getRole(b.mainHero.hero_id) ? getRole(b.mainHero.hero_id) : "";
    return (roleOrder[aRole] || 99) - (roleOrder[bRole] || 99);
  });

  // Generate HTML for each group.
  let html = "";
  groups.forEach(group => {
    const player = group.player;
    const isMVP = player.player_id === matchDetails.mvp.player_id;
    const isSVP = player.player_id === matchDetails.svp.player_id;

    // Build main row (always shown) using the mainHero.
    const mainHero = group.mainHero;
    if (!mainHero) return; // Skip if no hero info.
    // Use main hero's role for the role icon.
    const mainRole = mainHero.role ? mainHero.role.toLowerCase() : "";
    const mainRowClass = isMVP ? "mvp-row" : (isSVP ? "svp-row" : "");
    const nameDisp = player.nickname; // Always display for the main row.
    const dmgDisp = Math.round(player.damage_dealt);
    const blockedDisp = Math.round(player.damage_taken);
    const healDisp = Math.round(player.healing);
    let medalIconsHtml = "—";
    if (player.badges && player.badges.length > 0) {
      medalIconsHtml = generateMedals(player.badges);
    }
    const hitRateMain = mainHero.hit_rate ? Math.round(mainHero.hit_rate * 100) + "%" : "N/A";
    const roleIconPath = getRoleIcon(mainHero.hero_id);
    const mainHeroIconPath = getHeroIcon(mainHero.hero_id);
    let groupHtml = `
  <tbody>
    <tr class="${mainRowClass}">
      <td>
        <div class="player-cell-wrapper">
          <div class="player-cell">
            <div class="player-icons">
              ${roleIconPath ? `<div class="role-icon-container"><img class="highlight-role-icon" src="${roleIconPath}" alt="${mainHero.role}"></div>` : ""}
              <img class="hero-icon" src="${mainHeroIconPath}" alt="">
            </div>
          </div>
        </div>
      </td>
      <td>
        <div class="player-name">
          ${nameDisp} ${isMVP ? '<span class="mvp-badge">MVP</span>' : (isSVP ? '<span class="svp-badge">SVP</span>' : '')}
        </div>
      </td>
      <td>${mainHero.kills}</td>
      <td>${mainHero.deaths}</td>
      <td>${mainHero.assists}</td>
      <td>${medalIconsHtml}</td>
      <td>${dmgDisp}</td>
      <td>${blockedDisp}</td>
      <td>${healDisp}</td>
      <td>${hitRateMain}</td>
    </tr>
  </tbody>
`;
    // For each alt hero, generate a row inside a tbody with class "alt-row".
    group.altHeroes.forEach(hero => {
      const hitRateAlt = hero.hit_rate ? Math.round(hero.hit_rate * 100) + "%" : "N/A";
      const altRoleIconPath = getRoleIcon(hero.hero_id);
      const altHeroIconPath = getHeroIcon(hero.hero_id);
      groupHtml += `
    <tbody class="alt-row">
      <tr>
        <td>
          <div class="player-cell-wrapper">
            <div class="player-cell">
              <div class="player-icons">
                ${altRoleIconPath ? `<div class="role-icon-container"><img class="highlight-role-icon" src="${altRoleIconPath}" alt="${hero.role}"></div>` : ""}
                <img class="hero-icon" src="${altHeroIconPath}" alt="">
              </div>
            </div>
          </div>
        </td>
        <td>
          <div class="player-name"></div>
        </td>
        <td>${hero.kills}</td>
        <td>${hero.deaths}</td>
        <td>${hero.assists}</td>
        <td>—</td>
        <td></td>
        <td></td>
        <td></td>
        <td>${hitRateAlt}</td>
      </tr>
    </tbody>
  `;
    });
    html += groupHtml;
  });
  return html;
}

// Main function to fetch match details and update the accordion body.
function fetchFullMatchDetails(match, bodyElement) {
  fetch(`/data/matches/${match.match_uid}.json`)
    .then(response => response.json())
    .then(matchDetails => {
      const season = match.season || "N/A";
      const gamemode = matchDetails.game_mode.game_mode_name || "N/A";
      const timestampFormatted = formatTimestamp(match.match_timestamp);
      const durationText = match.duration ? formatDuration(match.duration) : "N/A";
      const mapText = match.map || "N/A";
      const replayID = matchDetails.replay_id || "N/A";

      // Group players based on win status.
      const winningPlayers = matchDetails.players.filter(p => p.is_win === true);
      const losingPlayers = matchDetails.players.filter(p => p.is_win === false);
      const victoryRows = generatePlayerHeroRows(winningPlayers, matchDetails);
      const defeatRows = generatePlayerHeroRows(losingPlayers, matchDetails);


      // Build the dynamic HTML content.
      const htmlContent = `
      <div class="highlight-match">
        <div class="match-header">
          <h1>Match <span id="match-id">${match.match_uid}</span></h1>
          <div class="details">
            <span><strong>Duration:</strong> ${durationText}</span>
            <span><strong>Map:</strong> ${mapText}</span>
            <span><strong>Replay ID:</strong> <span id="replay-id">${replayID}</span></span>
            <button id="copy-btn-${match.match_uid}" class="btn btn-sm btn-outline-light ms-2">Copy Replay ID</button>
          </div>
        </div>
        <!-- Victory Section -->
        <div class="team-section table-responsive">
          <table class="scoreboard-table">
            <thead>
              <tr>
                <th class="victory-title">VICTORY</th>
                <th>Player</th>
                <th>K</th>
                <th>D</th>
                <th>A</th>
                <th>Medals</th>
                <th>Damage</th>
                <th>Blocked</th>
                <th>Heal</th>
                <th>Hit Rate</th>
              </tr>
            </thead>
              ${victoryRows}
          </table>
        </div>
        <!-- Defeat Section -->
        <div class="team-section table-responsive">
          <table class="scoreboard-table">
            <thead>
              <tr>
                <th class="defeat-title">DEFEAT</th>
                <th>Player</th>
                <th>K</th>
                <th>D</th>
                <th>A</th>
                <th>Medals</th>
                <th>Damage</th>
                <th>Blocked</th>
                <th>Heal</th>
                <th>Accuracy</th>
              </tr>
            </thead>
              ${defeatRows}
          </table>
        </div>
      </div>
    `;
      bodyElement.innerHTML = htmlContent;
      bodyElement.setAttribute('data-loaded', 'true');
    })
    .catch(error => {
      bodyElement.innerHTML = `<p>Error loading match details.</p>`;
      console.error('Error fetching match details for', match.match_uid, error);
    });
}

// Fuzzy matching: Given a partial hero name, return candidate hero IDs.
function getHeroIdsByPartialName(partialName) {
  if (!heroData) return [];
  const term = partialName.trim().toLowerCase();
  return heroData
    .filter(h => h.name.toLowerCase().includes(term) ||
      (h.en_name && h.en_name.toLowerCase().includes(term)) ||
      (h.slug && h.slug.toLowerCase().includes(term)))
    .map(h => h.id);
}

// Filter matches based on team composition.
// teamHeroCandidates: an array where each element is an array of candidate hero IDs for a required team hero.
// opposingHeroCandidates: an array of candidate hero IDs for the opposing hero.
function getUnionMatches(candidateGroup, matchType) {
  const unionSet = new Set();
  candidateGroup.forEach(heroId => {
    if (heroesIndex[heroId] && Array.isArray(heroesIndex[heroId][matchType])) {
      heroesIndex[heroId][matchType].forEach(matchId => unionSet.add(matchId));
    }
  });
  return unionSet;
}


function getGroupMatches(candidateGroup, matchType) {
  if (!candidateGroup || candidateGroup.length === 0) return new Set();
  // For each hero in the candidate group, build a set of their match IDs.
  const heroMatchSets = candidateGroup.map(heroId => {
    if (heroesIndex[heroId] && Array.isArray(heroesIndex[heroId][matchType])) {
      return new Set(heroesIndex[heroId][matchType]);
    }
    return new Set();
  });
  // Return the intersection so that the match must include every hero in the group.
  return intersectSets(heroMatchSets);
}
// Helper function: Compute the intersection of an array of sets.
function intersectSets(sets) {
  if (sets.length === 0) return new Set();
  let intersection = sets[0];
  sets.slice(1).forEach(set => {
    intersection = new Set([...intersection].filter(matchId => set.has(matchId)));
  });
  return intersection;
}

function filterMatches(teamHeroCandidates, opposingHeroCandidates) {
    let teamMatches = null;
    let opposingMatches = null;
  
    // Only compute teamMatches if teamHeroCandidates are provided and non-empty.
    if (teamHeroCandidates &&
        teamHeroCandidates.length > 0 &&
        teamHeroCandidates.some(group => group.length > 0)) {
      const teamSets = teamHeroCandidates.map(candidateGroup => getGroupMatches(candidateGroup, "win"));
      teamMatches = intersectSets(teamSets);
    }
  
    // Only compute opposingMatches if opposingHeroCandidates are provided and non-empty.
    if (opposingHeroCandidates &&
        opposingHeroCandidates.length > 0 &&
        opposingHeroCandidates.some(group => group.length > 0)) {
      const opposingSets = opposingHeroCandidates.map(candidateGroup => getGroupMatches(candidateGroup, "loss"));
      opposingMatches = intersectSets(opposingSets);
    }
    // If both filters are provided, return the intersection.
    let filteredMatches;
    if (teamMatches && opposingMatches && teamMatches.size > 0 && opposingMatches.size > 0) {
      filteredMatches = new Set([...teamMatches].filter(matchId => opposingMatches.has(matchId)));
    } else if (teamMatches && teamMatches.size > 0) {
      filteredMatches = teamMatches;
    } else if (opposingMatches && opposingMatches.size > 0) {
      filteredMatches = opposingMatches;
    } else {
      filteredMatches = new Set(Object.keys(indexData));
    }

    const mapFilterEl = document.getElementById("mapFilter");
    const selectedMaps = Array.from(mapFilterEl.selectedOptions)
                            .map(option => option.value)
                            .filter(val => val !== "");
    if (selectedMaps.length > 0) {
        let unionMapMatches = new Set();
        selectedMaps.forEach(mapValue => {
            // Split the value in case it contains multiple IDs
            const mapIds = mapValue.split(",");
            mapIds.forEach(mapId => {
              if (mapIndex && mapIndex[mapId]) {
                mapIndex[mapId].forEach(matchId => unionMapMatches.add(matchId));
              }
            });
          });
        
        // Intersect the map matches with the previously filtered matches unless it's index data then just overwrite
        if (filteredMatches.size === Object.keys(indexData).length) {
            // Overwrite filteredMatches with the map union.
            filteredMatches = unionMapMatches;
          } else {
            // Otherwise, perform an intersection.
            filteredMatches = new Set([...filteredMatches].filter(matchId => unionMapMatches.has(matchId)));
          }
    }
    // -------------------------------------------
    return Array.from(filteredMatches);
  }



async function filterHeroes(){
  if (!heroesIndex) {
      try {
        const response = await fetch('/data/heroes_index.json');
        heroesIndex = await response.json();
      } catch (error) {
        console.error('Error lazy-loading heroesIndex:', error);
        alert('Error filtering data. Please try again later.');
        return;
      }
    }
  
    const teamSelected  = getSelectedHeroIds("teamHeroes");
    const opposingSelected  = getSelectedHeroIds("opposingHero");
  
      const teamHeroCandidates = teamSelected.length ? [teamSelected] : [];
      const opposingHeroCandidates = opposingSelected.length ? [opposingSelected] : [];  
  
    const filteredMatches = filterMatches(teamHeroCandidates, opposingHeroCandidates);
    // Fetch full match details for each match ID.
    const fullMatches = await Promise.all(filteredMatches.map(async matchUid => {
      try {
        const res = await fetch(`/data/matches/${matchUid}.json`);
        if (!res.ok) {
          if (res.status === 404) {
            console.warn(`Match file not found: /data/matches/${matchUid}.json`);
            return null; // Ignore missing files
          }
          throw new Error(`HTTP error! Status: ${res.status}`);
        }
        const matchDetails = await res.json();
        matchDetails.match_uid = matchUid; // Ensure match_uid is available
        return matchDetails;
      } catch (err) {
        console.error(`Error loading match details for ${matchUid}:`, err);
        return null;
      }
    }));
    const validFullMatches = fullMatches.filter(m => m !== null);
    renderMatches(validFullMatches);
}  

// Reset: Clear inputs and show all matches.
document.getElementById("resetBtn").addEventListener("click", function () {
    const teamInput = document.getElementById("teamHeroes");
    const opposingInput = document.getElementById("opposingHero");
    teamInput.value = "";
    opposingInput.value = "";
    selectedHeroes.teamHeroes = [];
    selectedHeroes.opposingHero = [];
    teamInput.selectpicker('deselectAll');
    opposingInput.selectpicker('deselectAll');
    renderMatches(Object.values(indexData));
});

$(document).ready(function() {
  $('.selectpicker').selectpicker();
});
