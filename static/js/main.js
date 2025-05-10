// static/js/main.js (lub profil_modal_filler.js)

document.addEventListener("DOMContentLoaded", function () {
  const modalEl = document.getElementById("exampleModal");
  if (!modalEl) {
    return;
  }

  const modalTitleSpanLocation = modalEl.querySelector("#modalRaidLocation");
  const modalTitleSpanTimestamp = modalEl.querySelector("#modalRaidTimestamp");
  const modalLoadingIndicatorEl = modalEl.querySelector("#modalLoadingState");
  const modalActualContentEl = modalEl.querySelector("#modalActualRaidContent");

  function formatNum(num, fractionDigits = 0) {
    if (
      num === null ||
      num === undefined ||
      num === "" ||
      isNaN(parseFloat(num))
    )
      return "N/A";
    return parseFloat(num).toLocaleString("pl-PL", {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    });
  }
  function formatNumOneDecimal(num) {
    return formatNum(num, 1);
  }

  function showElement(element, show = true) {
    if (element) {
      if (show) element.classList.remove("d-none");
      else element.classList.add("d-none");
    }
  }

  function updateModalText(elementId, text, defaultValue = "N/A") {
    if (!modalActualContentEl) return;
    const el = modalActualContentEl.querySelector(`#${elementId}`);
    if (el)
      el.textContent =
        text !== undefined &&
        text !== null &&
        text !== "" &&
        text.toString().trim() !== ""
          ? text
          : defaultValue;
  }

  modalEl.addEventListener("show.bs.modal", function (event) {
    const button = event.relatedTarget;
    if (!button) return;
    const raidPath = button.getAttribute("data-raid-path");
    if (!raidPath) return;

    showElement(modalLoadingIndicatorEl, true);
    showElement(modalActualContentEl, false);

    if (modalTitleSpanLocation)
      modalTitleSpanLocation.textContent = "Ładowanie...";
    if (modalTitleSpanTimestamp) modalTitleSpanTimestamp.textContent = "";

    const dynamicContentIdsToClear = [
      // Zaktualizowana lista do czyszczenia
      "#modalVictimsTableBody",
      "#modalKillerInfoContainer",
      "#modalRaidStatusVal",
      "#modalRaidExit",
      "#modalRaidClass",
      "#modalRaidTime",
      "#modalRaidPlayers",
      "#modalExpCalculated",
      "#modalExpJson",
      "#modalExpMultiplier",
      "#modalExpBonus",
      "#modalExpKill",
      "#modalExpLooting",
      "#modalExpExit",
      "#modalDmgDealt",
      "#modalDmgReceived",
      "#modalDistanceWalked",
      "#modalBloodloss",
      "#modalDmgReceivedByPartContent",
      "#modalSkillChangesList",
      "#modalItemsFoundCol",
      "#modalItemsLostCol",
    ];
    dynamicContentIdsToClear.forEach((selector) => {
      const el = modalActualContentEl.querySelector(selector);
      if (el) {
        if (
          el.tagName === "TBODY" ||
          el.tagName === "OL" ||
          el.id === "modalDmgReceivedByPartContent" ||
          el.id === "modalItemsFoundCol" ||
          el.id === "modalItemsLostCol" ||
          el.id === "modalSkillChangesList"
        ) {
          el.innerHTML = "";
        } else {
          el.textContent = "N/A";
        }
      }
    });
    showElement(
      modalActualContentEl.querySelector("#modalNoVictimsMsg"),
      false
    );
    showElement(
      modalActualContentEl.querySelector("#modalKillerInfoContainer"),
      false
    );
    showElement(
      modalActualContentEl.querySelector("#modalDmgReceivedByPartSection"),
      false
    );
    showElement(
      modalActualContentEl.querySelector("#modalSkillChangesListSection"),
      false
    );
    showElement(
      modalActualContentEl.querySelector("#modalItemsSection"),
      false
    );
    const cardStatusParentEl_reset = modalActualContentEl.querySelector(
      "#modalCardStatusParent"
    );
    if (cardStatusParentEl_reset) {
      cardStatusParentEl_reset.className = "card-body shadow-lg"; // Reset klas kolorów
    }

    fetch(`/api/raid_details_json?path=${encodeURIComponent(raidPath)}`)
      .then((response) => {
        if (!response.ok) {
          return response
            .json()
            .then((errData) => {
              throw new Error(
                errData.error || `Błąd serwera: ${response.status}`
              );
            })
            .catch(() => {
              throw new Error(
                `Błąd serwera: ${response.status} ${response.statusText}`
              );
            });
        }
        return response.json();
      })
      .then((responseData) => {
        if (responseData.error || !responseData.data) {
          if (modalTitleSpanLocation)
            modalTitleSpanLocation.textContent = "Błąd";
          if (modalTitleSpanTimestamp) modalTitleSpanTimestamp.textContent = "";
          modalActualContentEl.innerHTML = `<div class="alert alert-danger m-0">${
            responseData.error || "Nie udało się załadować danych."
          }</div>`;
          showElement(modalActualContentEl, true);
          showElement(modalLoadingIndicatorEl, false);
          return;
        }

        const d = responseData.data;

        if (modalTitleSpanLocation)
          modalTitleSpanLocation.textContent = d.location || "N/A";
        if (modalTitleSpanTimestamp)
          modalTitleSpanTimestamp.textContent = d.timestamp_formatted || "N/A";

        const victimsTableBodyEl = modalActualContentEl.querySelector(
          "#modalVictimsTableBody"
        );
        const noVictimsMsgEl =
          modalActualContentEl.querySelector("#modalNoVictimsMsg");
        if (victimsTableBodyEl) {
          if (d.victims && d.victims.length > 0) {
            d.victims.forEach((v, index) => {
              const row = victimsTableBodyEl.insertRow();
              row.innerHTML = `<th scope="row">${index + 1}</th><td>${
                v.Name || "N/A"
              }</td><td>${v.Level || "N/A"}</td><td>${
                v.RoleTranslated || "N/A"
              }</td><td>${v.WeaponName || "N/A"}</td><td>${
                v.DistanceFormatted || "N/A"
              }</td><td>${v.BodyPartTranslated || "N/A"}</td>`;
            });
            showElement(noVictimsMsgEl, false);
          } else {
            showElement(noVictimsMsgEl, true);
          }
        }

        const killerInfoContainerEl = modalActualContentEl.querySelector(
          "#modalKillerInfoContainer"
        );
        if (d.killer_info) {
          updateModalText("modalKillerName", d.killer_info.name);
          updateModalText("modalKillerRole", d.killer_info.role_translated);
          updateModalText("modalKillerSide", d.killer_info.side);
          updateModalText("modalKillerWeapon", d.killer_info.weapon_name);
          updateModalText(
            "modalKillerHitPart",
            d.killer_info.killed_by_part_translated
          );
          updateModalText(
            "modalKillerDmgAmount",
            formatNumOneDecimal(d.killer_info.lethal_damage_amount)
          );
          updateModalText(
            "modalKillerDmgType",
            d.killer_info.lethal_damage_type_translated
          );
          showElement(killerInfoContainerEl, true);
        } else {
          showElement(killerInfoContainerEl, false);
        }

        // --- POPRAWIONE KOLOROWANIE KARTY STATUSU ---
        const cardStatusParentEl = modalActualContentEl.querySelector(
          "#modalCardStatusParent"
        );
        const modalStatusValEl = modalActualContentEl.querySelector(
          "#modalRaidStatusVal"
        ); // Element h2 dla tekstu

        if (cardStatusParentEl && modalStatusValEl) {
          // Najpierw ustaw tekst statusu
          modalStatusValEl.textContent = d.raid_result || "N/A";

          // Reset klas kolorów
          cardStatusParentEl.className = "card-body shadow-lg"; // Twoje domyślne klasy dla tej karty

          let statusColorClassesToAdd =
            "text-secondary-emphasis bg-secondary-subtle border border-secondary-subtle"; // Domyślny szary

          // Użyj d.raw_raid_result dla logiki (bardziej niezawodne)
          const rawResult = d.raw_raid_result
            ? d.raw_raid_result.toLowerCase()
            : "";

          if (rawResult === "survived") {
            statusColorClassesToAdd =
              "text-success-emphasis bg-success-subtle border-success-subtle";
          } else if (rawResult === "runner") {
            statusColorClassesToAdd =
              "text-warning-emphasis bg-warning-subtle border-warning-subtle";
          } else if (
            rawResult === "killed" ||
            rawResult === "missinginaction"
          ) {
            statusColorClassesToAdd =
              "text-danger-emphasis bg-danger-subtle border-danger-subtle";
          }
          // Dodaj odpowiednie klasy do rodzica (div.card-body)
          cardStatusParentEl.classList.add(
            ...statusColorClassesToAdd.split(" ")
          );
        }
        // --- KONIEC POPRAWKI KOLOROWANIA ---

        const cardExitContainerEl = modalActualContentEl.querySelector(
          "#modalCardExitContainer"
        );
        if (d.exit_name && d.exit_name !== "---") {
          updateModalText("modalRaidExit", d.exit_name);
          showElement(cardExitContainerEl, true);
        } else {
          showElement(cardExitContainerEl, false);
        }
        updateModalText("modalRaidClass", d.survivor_class);
        updateModalText("modalRaidTime", d.play_time_formatted);
        const cardPlayersContainerEl = modalActualContentEl.querySelector(
          "#modalCardPlayersContainer"
        );
        if (d.player_count_in_raid && d.player_count_in_raid !== "N/A") {
          updateModalText("modalRaidPlayers", d.player_count_in_raid);
          showElement(cardPlayersContainerEl, true);
        } else {
          showElement(cardPlayersContainerEl, false);
        }

        updateModalText(
          "modalExpCalculated",
          formatNum(d.total_session_exp_calculated)
        );
        updateModalText(
          "modalExpJson",
          formatNum(d.total_session_exp_from_json)
        );
        updateModalText(
          "modalExpMultiplier",
          d.session_exp_mult !== undefined ? d.session_exp_mult + "x" : "N/A"
        );
        updateModalText(
          "modalExpBonus",
          d.experience_bonus_mult !== undefined
            ? d.experience_bonus_mult + "x"
            : "N/A"
        );
        updateModalText("modalExpKill", formatNum(d.session_stats?.exp_kill));
        updateModalText(
          "modalExpLooting",
          formatNum(d.session_stats?.exp_looting)
        );
        updateModalText(
          "modalExpExit",
          formatNum(d.session_stats?.exp_exit_status)
        );
        const sourceNoteEl = modalActualContentEl.querySelector(
          "#modalSessionStatsSourceNote"
        );
        if (sourceNoteEl)
          sourceNoteEl.textContent = d.session_stats_source_note || "";

        updateModalText(
          "modalDmgDealt",
          formatNum(d.session_stats?.damage_dealt)
        );
        const totalDmgReceived = d.session_stats?.damage_received_details
          ? Object.values(d.session_stats.damage_received_details).reduce(
              (a, b) => parseFloat(b) + a,
              0
            )
          : 0;
        updateModalText(
          "modalDmgReceived",
          formatNumOneDecimal(totalDmgReceived)
        );
        updateModalText(
          "modalDistanceWalked",
          d.session_stats?.distance_formatted
        );
        updateModalText(
          "modalBloodloss",
          d.session_stats?.blood_loss !== undefined
            ? d.session_stats.blood_loss
            : "N/A"
        );

        const dmgReceivedByPartSectionEl = modalActualContentEl.querySelector(
          "#modalDmgReceivedByPartSection"
        );
        const dmgReceivedByPartContentEl = modalActualContentEl.querySelector(
          "#modalDmgReceivedByPartContent"
        );
        if (
          dmgReceivedByPartContentEl &&
          d.session_stats?.damage_received_details &&
          totalDmgReceived > 0
        ) {
          let dmgPartHtml = "";
          for (const [part, dmg] of Object.entries(
            d.session_stats.damage_received_details
          )) {
            if (parseFloat(dmg) > 0) {
              dmgPartHtml += `<div class="col"><div class="card"><div class="card-body shadow"><h6>${part.toUpperCase()}</h6><hr class="my-1"><h3 class="text-danger">${formatNumOneDecimal(
                dmg
              )}</h3></div></div></div>`;
            }
          }
          dmgReceivedByPartContentEl.innerHTML = dmgPartHtml;
          showElement(dmgReceivedByPartSectionEl, true);
        } else {
          showElement(dmgReceivedByPartSectionEl, false);
        }

        // Logika dla zdrowia i witalności została usunięta z HTML, więc usuwamy ją też z JS

        const skillChangesContainerEl = modalActualContentEl.querySelector(
          "#modalSkillChangesListSection"
        );
        const skillChangesListEl = modalActualContentEl.querySelector(
          "#modalSkillChangesList"
        );
        if (
          skillChangesListEl &&
          d.skills_changed &&
          d.skills_changed.length > 0 &&
          d.skills_changed.some(
            (s) =>
              (s.SkillType === "Mastering" && parseFloat(s.Progress) > 0) ||
              (s.SkillType === "Common" &&
                parseFloat(s.PointsEarnedFormatted) !== 0 &&
                !isNaN(parseFloat(s.PointsEarnedFormatted)))
          )
        ) {
          skillChangesListEl.innerHTML = ""; // Wyczyść listę przed dodaniem
          d.skills_changed.forEach((skill) => {
            const points = parseFloat(skill.PointsEarnedFormatted);
            if (
              (skill.SkillType === "Mastering" &&
                parseFloat(skill.Progress) > 0) ||
              (skill.SkillType === "Common" && !isNaN(points) && points !== 0)
            ) {
              const li = document.createElement("li");
              li.className = "list-group-item p-1 ps-0";
              li.innerHTML = `${skill.SkillName}: Poziom ${skill.Progress} ${
                !isNaN(points) &&
                points !== 0 &&
                skill.PointsEarnedFormatted !== "N/A"
                  ? `(<span class="text-success fw-bold">+${skill.PointsEarnedFormatted}</span>)`
                  : ""
              }`;
              skillChangesListEl.appendChild(li);
            }
          });
          showElement(skillChangesContainerEl, true);
        } else {
          showElement(skillChangesContainerEl, false);
        }

        const itemsContainerEl =
          modalActualContentEl.querySelector("#modalItemsSection");
        const itemsFoundColEl = modalActualContentEl.querySelector(
          "#modalItemsFoundCol"
        );
        const itemsLostColEl =
          modalActualContentEl.querySelector("#modalItemsLostCol");
        let hasAnyItems = false;
        if (itemsFoundColEl && itemsLostColEl) {
          let foundHtml = "";
          if (d.found_in_raid_items && d.found_in_raid_items.length > 0) {
            hasAnyItems = true;
            foundHtml +=
              '<h6>Znalezione w rajdzie:</h6><ul class="list-unstyled mb-2 small">';
            d.found_in_raid_items.forEach(
              (item) => (foundHtml += `<li>${item.name} (x${item.count})</li>`)
            );
            foundHtml += "</ul>";
          }
          if (d.transfer_items && d.transfer_items.length > 0) {
            hasAnyItems = true;
            foundHtml +=
              '<h6>Przedmioty w kontenerze:</h6><ul class="list-unstyled mb-2 small">';
            d.transfer_items.forEach(
              (item) => (foundHtml += `<li>${item.name} (x${item.count})</li>`)
            );
            foundHtml += "</ul>";
          }
          itemsFoundColEl.innerHTML = foundHtml;
          let lostHtml = "";
          if (d.lost_insured_items && d.lost_insured_items.length > 0) {
            hasAnyItems = true;
            lostHtml +=
              '<h6>Stracone ubezpieczone:</h6><ul class="list-unstyled text-danger mb-2 small">';
            d.lost_insured_items.forEach(
              (item) => (lostHtml += `<li>${item.name} (x${item.count})</li>`)
            );
            lostHtml += "</ul>";
          }
          if (d.dropped_items && d.dropped_items.length > 0) {
            hasAnyItems = true;
            lostHtml +=
              '<h6>Upuszczone/Użyte:</h6><ul class="list-unstyled text-warning mb-2 small">';
            d.dropped_items.forEach(
              (item) => (lostHtml += `<li>${item.name} (x${item.count})</li>`)
            );
            lostHtml += "</ul>";
          }
          itemsLostColEl.innerHTML = lostHtml;
          showElement(itemsContainerEl, hasAnyItems);
        }

        showElement(modalLoadingIndicatorEl, false);
        showElement(modalActualContentEl, true);
      })
      .catch((error) => {
        console.error(
          "Błąd podczas pobierania lub przetwarzania szczegółów rajdu:",
          error
        );
        if (modalTitleSpanLocation) modalTitleSpanLocation.textContent = "Błąd";
        if (modalTitleSpanTimestamp)
          modalTitleSpanTimestamp.textContent = "ładowania";
        if (modalActualContentEl)
          modalActualContentEl.innerHTML = `<div class="alert alert-danger m-0">Nie udało się załadować szczegółów rajdu. Błąd: ${error.message}</div>`;
        showElement(modalActualContentEl, true);
        showElement(modalLoadingIndicatorEl, false);
      });
  });
});
