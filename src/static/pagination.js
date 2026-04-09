/**
 * OAPagination – reusable client-side pagination, filtering, sorting,
 * and lazy image loading engine for OverAchiever.
 *
 * Every paginated page calls this once with a configuration object.
 * The function wires up all event listeners and performs an initial
 * render so the caller never has to touch the DOM directly.
 *
 * @param {Object} opts - Configuration object (see properties below).
 *
 * @param {string}   opts.containerId
 *     ID of the wrapper element that holds every card.
 *
 * @param {string}   opts.cardSelector
 *     CSS selector that matches the individual item cards inside the
 *     container (e.g. ".game-card" or ".achievement").
 *
 * @param {number}   [opts.pageSize=50]
 *     How many items to show per page.
 *
 * @param {string}   [opts.searchInputId]
 *     ID of a text ``<input>`` used for free-text search.
 *
 * @param {string[]} [opts.searchAttrs=["data-name"]]
 *     Data-attribute names checked when filtering by the search query.
 *
 * @param {string}   [opts.sortSelectId]
 *     ID of a ``<select>`` whose value determines the active sort mode.
 *
 * @param {Object}   [opts.sortModes={}]
 *     A map of ``<option>`` values to *sort definitions*.  Each
 *     definition is either:
 *       - A comparator ``function(a, b) → number``, or
 *       - A descriptor ``{ attr, dir, type?, defaultVal? }`` where
 *         *attr* is a data-attribute name, *dir* is ``"asc"`` or
 *         ``"desc"``, *type* is ``"number"`` (default ``"string"``),
 *         and *defaultVal* is the fallback when the attribute is
 *         missing or unparseable.
 *
 * @param {string}   [opts.platformFilterId]
 *     ID of a ``<select>`` that filters cards by platform.  The value
 *     ``"all"`` disables the filter.
 *
 * @param {string}   [opts.platformAttr="data-platform"]
 *     Data-attribute that holds the platform slug on each card.
 *
 * @param {string}   [opts.hiddenClass]
 *     If set, cards are hidden by toggling this CSS class instead of
 *     setting ``display: none`` inline.
 *
 * @param {string}   [opts.noResultsId]
 *     ID of a "no results" element shown when the filtered list is
 *     empty.
 *
 * @param {string}   [opts.countId]
 *     ID of an element whose ``textContent`` is updated with the
 *     visible item count (e.g. "42 achievements").
 *
 * @param {string}   [opts.countSuffix="item"]
 *     Singular noun appended to the count (an "s" is added
 *     automatically for plurals).
 *
 * @param {Object}   [opts.sections]
 *     Grouped-section configuration used to show / hide section
 *     headers when a particular sort mode is active.
 *     Shape:
 *       {
 *         attr:          string,     // data-attribute that groups cards
 *         groupSortMode: string,     // sortModes key that triggers grouping
 *         order:         string[],   // group keys in display order
 *         headers: {
 *           [key]: { headerId: string, countId?: string }
 *         }
 *       }
 */
function OAPagination(opts) {
    "use strict";

    var PAGE_SIZE = opts.pageSize || 10;

    var container = document.getElementById(opts.containerId);
    if (!container) {
        return;
    }

    var allCards = Array.prototype.slice.call(
        container.querySelectorAll(opts.cardSelector),
    );
    if (!allCards.length) {
        return;
    }

    /* ---- cached element references ---- */

    var searchInput = opts.searchInputId
        ? document.getElementById(opts.searchInputId)
        : null;
    var sortSelect = opts.sortSelectId
        ? document.getElementById(opts.sortSelectId)
        : null;
    var platformFilter = opts.platformFilterId
        ? document.getElementById(opts.platformFilterId)
        : null;
    var noResultsEl = opts.noResultsId
        ? document.getElementById(opts.noResultsId)
        : null;
    var countEl = opts.countId ? document.getElementById(opts.countId) : null;

    var paginationEl = document.getElementById("pagination");
    var pageInfoEl = document.getElementById("page-info");
    var pagePrevEl = document.getElementById("page-prev");
    var pageNextEl = document.getElementById("page-next");

    var searchAttrs = opts.searchAttrs || ["data-name"];
    var platformAttr = opts.platformAttr || "data-platform";
    var hiddenClass = opts.hiddenClass || null;
    var sortModes = opts.sortModes || {};
    var sections = opts.sections || null;
    var countSuffix = opts.countSuffix || "item";

    var currentPage = 1;

    /* ================================================================
     * Helpers
     * ============================================================= */

    /** Hide a single card element. */
    function hideCard(card) {
        if (hiddenClass) {
            card.classList.add(hiddenClass);
        } else {
            card.style.display = "none";
        }
    }

    /** Show a single card element. */
    function showCard(card) {
        if (hiddenClass) {
            card.classList.remove(hiddenClass);
        } else {
            card.style.display = "";
        }
    }

    /**
     * Swap every ``data-src`` attribute to ``src`` inside *card* so
     * that the browser actually downloads the image.  Once activated
     * the ``data-src`` attribute is removed so the swap is a no-op on
     * subsequent renders.
     */
    function activateImages(card) {
        var imgs = card.querySelectorAll("img[data-src]");
        for (var i = 0; i < imgs.length; i++) {
            imgs[i].setAttribute("src", imgs[i].getAttribute("data-src"));
            imgs[i].removeAttribute("data-src");
        }
    }

    /* ================================================================
     * Filtering
     * ============================================================= */

    /** Return the subset of ``allCards`` matching all active filters. */
    function getFilteredCards() {
        var result = allCards;

        /* -- text search -- */
        if (searchInput) {
            var query = searchInput.value.toLowerCase().trim();
            if (query) {
                result = result.filter(function (card) {
                    for (var j = 0; j < searchAttrs.length; j++) {
                        var val = card.getAttribute(searchAttrs[j]) || "";
                        if (val.indexOf(query) !== -1) {
                            return true;
                        }
                    }
                    return false;
                });
            }
        }

        /* -- platform select -- */
        if (platformFilter) {
            var plat = platformFilter.value;
            if (plat && plat !== "all") {
                result = result.filter(function (card) {
                    return (card.getAttribute(platformAttr) || "") === plat;
                });
            }
        }

        return result;
    }

    /* ================================================================
     * Sorting
     * ============================================================= */

    /**
     * Return a **new** array with *cardList* sorted according to the
     * currently selected sort mode.
     */
    function sortCards(cardList) {
        if (!sortSelect) {
            return cardList;
        }

        var mode = sortSelect.value;
        var config = sortModes[mode];
        if (!config) {
            return cardList;
        }

        var sorted = cardList.slice();

        if (typeof config === "function") {
            sorted.sort(config);
        } else {
            var attr = config.attr;
            var dir = config.dir === "desc" ? -1 : 1;
            var isNum = config.type === "number";
            var defVal =
                config.defaultVal !== undefined
                    ? config.defaultVal
                    : isNum
                      ? 0
                      : "";

            sorted.sort(function (a, b) {
                var va = a.getAttribute(attr);
                var vb = b.getAttribute(attr);

                if (isNum) {
                    va = parseFloat(va);
                    vb = parseFloat(vb);
                    if (isNaN(va)) {
                        va = defVal;
                    }
                    if (isNaN(vb)) {
                        vb = defVal;
                    }
                    return (va - vb) * dir;
                }

                va = va || defVal;
                vb = vb || defVal;
                return va.localeCompare(vb) * dir;
            });
        }

        return sorted;
    }

    /* ================================================================
     * Render
     * ============================================================= */

    /**
     * Main render loop: filter → sort → paginate → update DOM.
     *
     * Called on every user interaction (search keystroke, sort/filter
     * change, page button click) and once at startup.
     */
    function render() {
        var filtered = getFilteredCards();
        var sorted = sortCards(filtered);
        var total = sorted.length;
        var totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

        if (currentPage > totalPages) {
            currentPage = totalPages;
        }
        if (currentPage < 1) {
            currentPage = 1;
        }

        var start = (currentPage - 1) * PAGE_SIZE;
        var end = Math.min(start + PAGE_SIZE, total);
        var pageCards = sorted.slice(start, end);

        var i, k, key, headerEl, cntEl;

        /* -- 1. hide every card -- */
        for (i = 0; i < allCards.length; i++) {
            hideCard(allCards[i]);
        }

        /* -- 2. position cards & optional section headers -- */
        var mode = sortSelect ? sortSelect.value : "";

        if (sections && mode === sections.groupSortMode) {
            /* Grouped mode: count per-group totals, split page cards
               by group, then render each group with its header. */
            var groupTotals = {};
            var groupPage = {};

            for (k = 0; k < sections.order.length; k++) {
                key = sections.order[k];
                groupTotals[key] = 0;
                groupPage[key] = [];
            }

            for (i = 0; i < sorted.length; i++) {
                var sk1 = sorted[i].getAttribute(sections.attr);
                if (groupTotals[sk1] !== undefined) {
                    groupTotals[sk1]++;
                }
            }

            for (i = 0; i < pageCards.length; i++) {
                var sk2 = pageCards[i].getAttribute(sections.attr);
                if (groupPage[sk2]) {
                    groupPage[sk2].push(pageCards[i]);
                }
            }

            for (k = 0; k < sections.order.length; k++) {
                key = sections.order[k];
                headerEl = document.getElementById(
                    sections.headers[key].headerId,
                );
                cntEl = sections.headers[key].countId
                    ? document.getElementById(sections.headers[key].countId)
                    : null;

                if (!headerEl) {
                    continue;
                }

                if (groupPage[key].length > 0) {
                    headerEl.style.display = "";
                    if (cntEl) {
                        cntEl.textContent = "(" + groupTotals[key] + ")";
                    }
                    container.appendChild(headerEl);
                    for (var j = 0; j < groupPage[key].length; j++) {
                        container.appendChild(groupPage[key][j]);
                        showCard(groupPage[key][j]);
                        activateImages(groupPage[key][j]);
                    }
                } else {
                    headerEl.style.display = "none";
                }
            }
        } else {
            /* Flat mode: hide every section header, re-append sorted
               cards so the DOM order matches the sort, then reveal
               only the current page slice. */
            if (sections) {
                for (k = 0; k < sections.order.length; k++) {
                    headerEl = document.getElementById(
                        sections.headers[sections.order[k]].headerId,
                    );
                    if (headerEl) {
                        headerEl.style.display = "none";
                    }
                }
            }

            for (i = 0; i < sorted.length; i++) {
                container.appendChild(sorted[i]);
            }

            for (i = 0; i < pageCards.length; i++) {
                showCard(pageCards[i]);
                activateImages(pageCards[i]);
            }
        }

        /* -- 3. no-results message -- */
        if (noResultsEl) {
            container.appendChild(noResultsEl);
            noResultsEl.style.display = total === 0 ? "" : "none";
        }

        /* -- 4. visible-count label -- */
        if (countEl) {
            countEl.textContent =
                total + " " + countSuffix + (total === 1 ? "" : "s");
        }

        /* -- 5. pagination controls -- */
        if (paginationEl) {
            paginationEl.style.display = totalPages <= 1 ? "none" : "";
        }
        if (pageInfoEl) {
            pageInfoEl.textContent =
                "Page " + currentPage + " of " + totalPages;
        }
        if (pagePrevEl) {
            pagePrevEl.disabled = currentPage <= 1;
        }
        if (pageNextEl) {
            pageNextEl.disabled = currentPage >= totalPages;
        }
    }

    /* ================================================================
     * Event listeners
     * ============================================================= */

    if (searchInput) {
        searchInput.addEventListener("input", function () {
            currentPage = 1;
            render();
        });
    }

    if (sortSelect) {
        sortSelect.addEventListener("change", function () {
            currentPage = 1;
            render();
        });
    }

    if (platformFilter) {
        platformFilter.addEventListener("change", function () {
            currentPage = 1;
            render();
        });
    }

    if (pagePrevEl) {
        pagePrevEl.addEventListener("click", function () {
            if (currentPage > 1) {
                currentPage--;
                render();
                container.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                });
            }
        });
    }

    if (pageNextEl) {
        pageNextEl.addEventListener("click", function () {
            var tp = Math.max(
                1,
                Math.ceil(getFilteredCards().length / PAGE_SIZE),
            );
            if (currentPage < tp) {
                currentPage++;
                render();
                container.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                });
            }
        });
    }

    /* ---- initial render ---- */
    render();
}
