const modWindow = document.getElementById('modal-window')
const modOverlay = document.getElementById('modal-overlay')
const pickerWindow = document.getElementById('picker-window')
const pickerOverlay = document.getElementById('picker-overlay')

const uid = window.location.pathname.split('/').at(-1)
const typeID = Object.freeze({translation: 1, correction: 2, original: 3})
const sortID = Object.freeze({az: 1, latest: 2, words: 3})

let isOriginal = true
let timeoutID = 0
let originalPageCount = parseInt($("#page-selector").children().last().text())

let currentData = {}
let isSearching = false
let currentPage = 0
let currentSorting = "latest"
let currentType = "translation"
let searchQuery = ""

// ===== MODAL FUNCTIONS =====

function clickOut(e) {
    if(!modWindow.contains(e.target)) {
        deleteModalClose()
    }
}

function deleteModalClose() {
    //$("body").css("overflow-y", "scroll") // Re-enable body scrolling
    $("#modal-overlay").fadeOut(200)
    $(window).off("click", clickOut)
}

function deleteModalOpen(articleId, articleName, correction=false) {
    //$("body").css("overflow-y", "hidden")   // Disable body scrolling while the modal is open
    $("#confirm-text").text(`Chcete smazat ${correction ? "korekci" : "článek"} "${articleName.trim()}"?`)
    if(correction) {
        $("#btn-delete-yes").on("click", () => unassignCorrection(articleId))
    } else {
        $("#btn-delete-yes").on("click", () => deleteArticle(articleId))
    }
    $("#modal-overlay").css("display", "flex").hide().fadeIn(200)
    setTimeout(() => $(window).on("click", clickOut), 100)  // Wait for a bit so the event doesn't fire from the current click
}

function deleteArticle(id) {
    fetch(`/article/${id}/delete`, {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        }
    }).then(() => window.location.reload())
}

function clickOut(e) {
    if(!pickerWindow.contains(e.target)) {
        articlePickerClose()
    }
}

function articlePickerClose() {
    $("#picker-overlay").fadeOut(200)
    $(window).off("click", clickOut)
    $('#input-search').off('input', handlePickerSearch)
}

function articlePickerOpen() {
    $("#picker-overlay").css("display", "flex").hide().fadeIn(200)
    setTimeout(() => $(window).on("click", clickOut), 100)
    $('#input-search').on('input', handlePickerSearch).val("")
}

// ===== SEARCH FUNCTIONS =====

function setPageCount(count) {
    $("#page-selector").empty()
    for(let i = 0; i < count; i++) {
        $("<span>", {
            class: `px-2 py-2 transition-all rounded-md ${i == currentPage ? "bg-white/10" : "hover:bg-white/30"}`,
            text: i+1,
        }).appendTo("#page-selector").on("click", () => {showPage(i)})
    }
}

function setSelectedPage(x) {
    currentPage = x
    $("#page-selector").children().removeClass('bg-white/10')
    $("#page-selector").children().eq(x).addClass('bg-white/10')
}

async function showPage(page) {
    setSelectedPage(page)
    let searchPromise
    if(isSearching) {
        searchPromise = fetch(`/api/search/article?` + new URLSearchParams({
            q: searchQuery,
            u: uid,
            o: currentType == 'original' ? 1 : 0,
            s: currentSorting,
            format: 'html',
            p: page
        }))
    } else {
        searchPromise = fetch(`/api/user/${uid}/articles?` + new URLSearchParams({
            p: page,
            t: currentType,
            s: currentSorting,
            format: 'html'
            }))
    }

    searchPromise.then(data => data.text())
    .then(html => {
        $('#article-table').replaceWith(html)
    })
}

function setSorting(order) {
    currentSorting = order
    $("#sort-selector").children().removeClass('bg-white/30')
    $("#sort-selector").children().eq(sortID[order]).addClass('bg-white/30')
    showPage(0)
}

function searchArticle(query) {
    if (query == "" || query.length <= 2) {
        if(isSearching) {
            isSearching = false
            fetch(`/api/user/${uid}/articles?` + new URLSearchParams({
                t: currentType,
                format: 'count_only'
            })).then(data => data.json())
            .then(json => {
                setPageCount(json.result.count / json.result.per_page)
            })
            showPage(0)
        }
        return
    }
    isSearching = true
    searchQuery = query
    $('.usr-row').animate({opacity: 0}, 300)
    fetch(`/api/search/article?` + new URLSearchParams({
            q: searchQuery,
            u: uid,
            format: 'count_only'
        })).then(response => response.json())
        .then(json => {
            setPageCount(json.result.count / json.result.per_page)
        })
    showPage(0)
}

async function setType(type) {
    currentType = type
    $("#type-selector").children().removeClass('bg-white/30')
    $("#type-selector").children().eq(typeID[type]).addClass('bg-white/30')
    fetch(`/api/user/${uid}/articles?` + new URLSearchParams({
        t: currentType,
        format: 'count_only'
    })).then(data => data.json())
    .then(json => {
        setPageCount(json.result.count / json.result.per_page)
    })
    showPage(0)
}

function handleSearch(e) {
    clearTimeout(timeoutID)
    if(e.target.value.length > 1) {
        timeoutID = setTimeout(searchArticle, 300, e.target.value)
    } else {
        searchArticle(e.target.value)
    }
}

// ===== ARTICLE PICKER FUNCTIONS =====

function addPickerItem(row) {
    const template = $('#search-result-template')
    let newRow = template.contents().clone(true, true)
    newRow.find('#result-name').text(row.name)
    let authorLink = $("<a>", {
        class: "underline",
        href: `/user/${row.author.id}`,
        text: row.author.name})
    newRow.find('#result-author').append(authorLink)
    newRow.find('#result-corrector').text(row.corrector.name)
    newRow.find('#btn-pick').on('click', () => bindCorrection(row.id))
    $('#result-table-body').append(newRow)
}

function bindCorrection(articleId) {
    const data = new URLSearchParams({aid: articleId})
    fetch(`/api/user/${uid}/assign-correction`, {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        },
        body: data
    }).then(() => window.location.reload())
}

function unassignCorrection(articleId) {
    fetch(`/api/article/${articleId}/remove-correction`, {
        method: "POST"
    }).then(() => window.location.reload())
}

function searchPickerArticle(query) {
    $('#result-table-body').empty()
    fetch('/api/search/article?' + new URLSearchParams({
        'q': query
    })).then(response => response.json()).then(r => r.result.slice(0, 10).forEach(result => addPickerItem(result)))
}

function handlePickerSearch(e) {
    clearTimeout(timeoutID)
    if(e.target.value.length > 2) {
        timeoutID = setTimeout(searchPickerArticle, 300, e.target.value)
    }
}

$("#search-field").on("input", handleSearch)
setSelectedPage(0)
setSelectedSorter('latest')
setSelectedType('translation')
