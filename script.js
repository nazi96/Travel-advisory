/* global travelAdvisories, advisoryLevels, regions */

(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────
  let filtered = [...travelAdvisories];
  let activeLevel = null; // null = show all

  // ── DOM References ─────────────────────────────────────
  const searchInput   = document.getElementById("searchInput");
  const regionFilter  = document.getElementById("regionFilter");
  const levelFilter   = document.getElementById("levelFilter");
  const grid          = document.getElementById("cardsGrid");
  const resultsCount  = document.getElementById("resultsCount");
  const modalOverlay  = document.getElementById("modalOverlay");
  const modalContent  = document.getElementById("modalContent");
  const legendItems   = document.querySelectorAll(".legend-item");

  // ── Bootstrap ─────────────────────────────────────────
  populateRegions();
  renderCards(travelAdvisories);
  attachListeners();

  // ── Populate region dropdown ───────────────────────────
  function populateRegions() {
    regions.forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r === "All Regions" ? "" : r;
      opt.textContent = r;
      regionFilter.appendChild(opt);
    });
  }

  // ── Filtering logic ────────────────────────────────────
  function applyFilters() {
    const query   = searchInput.value.trim().toLowerCase();
    const region  = regionFilter.value;
    const level   = levelFilter.value ? parseInt(levelFilter.value, 10) : null;

    filtered = travelAdvisories.filter((advisory) => {
      const matchesQuery  = !query || advisory.country.toLowerCase().includes(query) || advisory.region.toLowerCase().includes(query);
      const matchesRegion = !region || advisory.region === region;
      const matchesLevel  = level === null ? (activeLevel === null || advisory.level === activeLevel) : advisory.level === level;
      return matchesQuery && matchesRegion && matchesLevel;
    });

    renderCards(filtered);
  }

  // ── Render card grid ───────────────────────────────────
  function renderCards(list) {
    grid.innerHTML = "";

    resultsCount.textContent = `Showing ${list.length} of ${travelAdvisories.length} destinations`;

    if (list.length === 0) {
      grid.innerHTML = `
        <div class="no-results">
          <span class="icon">🔍</span>
          <p>No destinations match your search. Try adjusting your filters.</p>
        </div>`;
      return;
    }

    list.forEach((country) => {
      const lvl  = advisoryLevels[country.level];
      const card = document.createElement("article");
      card.className = "card";
      card.setAttribute("role", "button");
      card.setAttribute("tabindex", "0");
      card.setAttribute("aria-label", `${country.country} – Level ${country.level}: ${lvl.label}`);

      card.innerHTML = `
        <div class="card-header">
          <span class="card-flag" aria-hidden="true">${country.flag}</span>
          <div class="card-title">
            <h2>${country.country}</h2>
            <span>${country.region}</span>
          </div>
          <span class="level-badge" style="background:${lvl.bg};color:${lvl.color};">
            ${lvl.icon} Level ${country.level}
          </span>
        </div>
        <div class="card-body">
          <p>${country.summary}</p>
        </div>
        <div class="card-footer">
          <span>Updated ${formatDate(country.lastUpdated)}</span>
          <a href="#" class="details-link" aria-label="View details for ${country.country}">View details →</a>
        </div>`;

      card.addEventListener("click", () => openModal(country));
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openModal(country); }
      });

      grid.appendChild(card);
    });
  }

  // ── Modal ──────────────────────────────────────────────
  function openModal(country) {
    const lvl = advisoryLevels[country.level];

    modalContent.innerHTML = `
      <div class="modal-top">
        <span class="modal-flag" aria-hidden="true">${country.flag}</span>
        <div class="modal-heading">
          <h2>${country.country}</h2>
          <p class="region-tag">${country.region} &nbsp;·&nbsp; ${country.language}</p>
          <span class="modal-level-badge" style="background:${lvl.bg};color:${lvl.color};">
            ${lvl.icon} Level ${country.level} – ${lvl.label}
          </span>
        </div>
        <button class="modal-close" id="modalClose" aria-label="Close modal">✕</button>
      </div>

      <div class="modal-body">
        <p class="modal-summary">${country.summary}</p>

        <div class="info-grid">
          <div class="info-item">
            <div class="label">Currency</div>
            <div class="value">${country.currency}</div>
          </div>
          <div class="info-item">
            <div class="label">Visa</div>
            <div class="value">${country.visa}</div>
          </div>
        </div>

        <div class="modal-section" style="margin-top:1.1rem;">
          <h3>🛡️ Safety Tips</h3>
          <ul>${country.tips.map((t) => `<li>${t}</li>`).join("")}</ul>
        </div>

        <div class="modal-section">
          <h3>💊 Health Advisory</h3>
          <ul>${country.health.map((h) => `<li>${h}</li>`).join("")}</ul>
        </div>

        <div class="modal-section">
          <h3>🚨 Emergency Contacts</h3>
          <div class="emergency-grid">
            <div class="emergency-item">
              <div>
                <div class="e-label">Police</div>
                <div class="e-number">${country.emergency.police}</div>
              </div>
            </div>
            <div class="emergency-item">
              <div>
                <div class="e-label">Ambulance</div>
                <div class="e-number">${country.emergency.ambulance}</div>
              </div>
            </div>
            <div class="emergency-item">
              <div>
                <div class="e-label">Fire</div>
                <div class="e-number">${country.emergency.fire}</div>
              </div>
            </div>
            <div class="emergency-item">
              <div>
                <div class="e-label">US Embassy</div>
                <div class="e-number" style="font-size:0.78rem;word-break:break-word;">${country.emergency.embassy}</div>
              </div>
            </div>
          </div>
        </div>

        <p class="last-updated">Advisory last updated: ${formatDate(country.lastUpdated)}</p>
      </div>`;

    modalOverlay.classList.add("open");
    document.body.style.overflow = "hidden";

    document.getElementById("modalClose").addEventListener("click", closeModal);

    // Trap focus on close button when modal opens
    setTimeout(() => document.getElementById("modalClose").focus(), 50);
  }

  function closeModal() {
    modalOverlay.classList.remove("open");
    document.body.style.overflow = "";
  }

  // ── Legend level filter ────────────────────────────────
  legendItems.forEach((item) => {
    item.addEventListener("click", () => {
      const lvl = parseInt(item.dataset.level, 10);
      if (activeLevel === lvl) {
        // deselect
        activeLevel = null;
        item.classList.remove("active");
        levelFilter.value = "";
      } else {
        activeLevel = lvl;
        legendItems.forEach((el) => el.classList.remove("active"));
        item.classList.add("active");
        levelFilter.value = String(lvl);
      }
      applyFilters();
    });
  });

  // ── Event listeners ────────────────────────────────────
  function attachListeners() {
    searchInput.addEventListener("input", applyFilters);
    regionFilter.addEventListener("change", applyFilters);
    levelFilter.addEventListener("change", () => {
      if (levelFilter.value) {
        const lvl = parseInt(levelFilter.value, 10);
        activeLevel = lvl;
        legendItems.forEach((el) => {
          el.classList.toggle("active", parseInt(el.dataset.level, 10) === lvl);
        });
      } else {
        activeLevel = null;
        legendItems.forEach((el) => el.classList.remove("active"));
      }
      applyFilters();
    });

    // Close modal on overlay click
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) closeModal();
    });

    // Close modal on Escape
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modalOverlay.classList.contains("open")) closeModal();
    });
  }

  // ── Helpers ────────────────────────────────────────────
  function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
  }
})();
