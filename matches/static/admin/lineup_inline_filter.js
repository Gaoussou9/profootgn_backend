// static/admin/lineup_inline_filter.js
// Refiltre le <select name="-player"> d'une ligne d'inline quand on change le club
(function () {
  function onClubChange(e) {
    const selectClub = e.target;
    const row =
      selectClub.closest("tr") ||
      selectClub.closest(".dynamic-lineup_set") ||
      selectClub.closest(".inline-related");
    if (!row) return;

    // Champ "player" de la même ligne
    const playerSelect =
      row.querySelector('select[name$="-player"]') ||
      row.querySelector('select[id$="-player"]');
    if (!playerSelect) return;

    const clubId = selectClub.value;
    if (!clubId) {
      playerSelect.innerHTML = '<option value="">---------</option>';
      return;
    }

    // Appelle notre API publique pour récupérer les joueurs du club
    fetch(`/api/players/search/?club=${clubId}&limit=200`, { credentials: "same-origin" })
      .then((r) => (r.ok ? r.json() : []))
      .then((list) => {
        const opts = ['<option value="">---------</option>'];
        (list || []).forEach((p) => {
          // p = {id, name, club_id, club_name}
          opts.push(`<option value="${p.id}">${p.name}</option>`);
        });
        playerSelect.innerHTML = opts.join("");
      })
      .catch(() => {
        // silencieux
      });
  }

  function bindAll(scope) {
    const root = scope || document;
    // cible les selects "club" des lignes d'inline Tabular
    root
      .querySelectorAll(
        'tr select[name$="-club"], .dynamic-lineup_set select[name$="-club"], .inline-related select[name$="-club"]'
      )
      .forEach((sel) => {
        sel.removeEventListener("change", onClubChange);
        sel.addEventListener("change", onClubChange);
      });
  }

  document.addEventListener("DOMContentLoaded", () => bindAll(document));

  // Django admin émet 'formset:added' quand on ajoute une ligne inline
  document.body.addEventListener("formset:added", (e) => {
    bindAll(e.target);
  });
})();
