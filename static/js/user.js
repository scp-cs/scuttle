const modWindow = document.getElementById('modal-window')
const modOverlay = document.getElementById('modal-overlay')
const pickerWindow = document.getElementById('picker-window')
const pickerOverlay = document.getElementById('picker-overlay')

const uid = window.location.pathname.split('/').at(-1)

let isOriginal = true
let timeoutID = 0
let originalPageCount = parseInt($("#page-selector").children().last().text())

let currentData = {}
let isSearching = false
let currentPage = 0
let currentSorting = "latest"

let currentType = "translation"

// ===== UTILITY FUNCTIONS ======

/**
 * Accepts a parsable date string and converts it to the "cs-CZ" locale format
 * @param {string} dateString 
 * @returns string
 */
function dateAsLocal(dateString) {
    const date = new Date(Date.parse(dateString))
    return date.toLocaleString("cs-CZ", {year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"})
}

/**
 * Adds or changes a URL GET parameter and reloads the page
 * @param {string} key The key to be added / changed
 * @param {string} value The value to set
 */
function addGetParam(key, value) {
    let currentLocation = new URL(window.location.href)
    currentLocation.searchParams.set(key, value)
    window.location = currentLocation.toString()
}

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

function setSelectedSorter(sort) {
    let x;
    switch (sort) {
        case 'az':
            x = 1
            break;
        
        case 'latest':
            x = 2
            break;

        case 'words':
            x = 3
            break;

        default:
            break;
    }
    $("#sort-selector").children().removeClass('bg-white/30')
    $("#sort-selector").children().eq(x).addClass('bg-white/30')
}

function setSelectedType(type) {
    let x;
    switch (type) {
        case 'translation':
            x = 1
            break;
        
        case 'correction':
            x = 2
            break;

        case 'original':
            x = 3
            break;

        default:
            break;
    }
    $("#type-selector").children().removeClass('bg-white/30')
    $("#type-selector").children().eq(x).addClass('bg-white/30')
}

async function showPage(page) {
    setSelectedPage(page)
    if(isSearching) {
        addRows(currentData.result
            .slice(page*15, (page+1)*15), currentData.hasAuth)
    } else {
        await fetchPage(page, currentSorting, currentType).then(data => {
            debugger
            setPageCount(Math.ceil(data.total/15))
            addRows(data.result, data.hasAuth)
        })  
    }
}

function addRows(rows, hasAuth) {
    switch (currentType) {
        case 'translation':
            $('#tb-articles').empty()
            rows.forEach(row => {addTranslationRow(row, hasAuth)})
            break;

        case 'correction':
            $('#co-articles').empty()
            rows.forEach(row => {addCorrectionRow(row, hasAuth)})
            break;
        
        case 'original':
            $('#or-articles').empty()
            rows.forEach(row => {addOriginalRow(row, hasAuth)})
            break;

        default:
            break;
    }
}

function setSorting(order) {
    setSelectedSorter(order)
    if(isSearching) {
        switch (order) {
            case 'az':
                currentData.result.sort((a, b) => a.name.localeCompare(b.name, undefined, {numeric: true}))
                break
            case 'latest':
                currentData.result.sort((a, b) => {return Date.parse(b.added) - Date.parse(a.added)})
                break
            case 'words':
                currentData.result.sort((a, b) => b.words - a.words)
            default:
                break
        }
        showPage(0)
    } else {
        currentSorting = order
        showPage(0)
    }
}

function addTranslationRow(article, hasAuth) {
    let template = $("#translation-row-template").contents().clone(true, true)

    if(article.link) {
        let link = $("<a>", {
            class: "hover:underline",
            href: article.link,
            target: "_blank",
            text: article.name})
        template.find("#translation-name").append(link)
    } else {
        template.find("#translation-name").addClass("text-gray-500").text(article.name)
    }
    template.find('#translation-bonus').text(article.bonus)
    template.find('#translation-words').text(article.words)
    
    if(article.corrector) {
        let link = $("<a>", {
            class: "underline",
            href: `/user/${article.corrector.id}`,
            text: article.corrector.nickname})
        template.find("#translation-corrector").append(link)
    } else {
        template.find("#translation-corrector").text("N/A")
    }

    template.find("#translation-timestamp").text(dateAsLocal(article.added))
    
    if(hasAuth) {
        let action_template = $("#translation-actions-template").contents().clone(true, true)
        action_template.find("#translation-edit").prop("href", `/article/${article.id}/edit`)
        action_template.find("#translation-delete").on("click", () => {deleteModalOpen(article.id, article.name)})
        template.append(action_template)
    }

    $("#tb-articles").append(template)
}

function addOriginalRow(article, hasAuth) {
    let template = $("#original-row-template").contents().clone(true, true)

    if(article.link) {
        let link = $("<a>", {
            class: "hover:underline",
            href: article.link,
            target: "_blank",
            text: article.name})
        template.find("#article-name").append(link)
    } else {
        template.find("#article-name").addClass("text-gray-500").text(article.name)
    }
    template.find('#article-words').text(article.words)
    
    if(article.corrector) {
        let link = $("<a>", {
            class: "underline",
            href: `/user/${article.corrector.id}`,
            text: article.corrector.nickname})
        template.find("#article-corrector").append(link)
    } else {
        template.find("#article-corrector").text("N/A")
    }

    template.find("#article-timestamp").text(dateAsLocal(article.added))
    
    if(hasAuth) {
        let action_template = $("#translation-actions-template").contents().clone(true, true)
        action_template.find("#translation-edit").prop("href", `/article/${article.id}/edit`)
        action_template.find("#translation-delete").on("click", () => {deleteModalOpen(article.id, article.name)})
        template.append(action_template)
    }

    $("#or-articles").append(template)
}

function addCorrectionRow(correction, hasAuth) {
    let template = $('#correction-row-template').contents().clone(true, true)
    //template.find('#correction-name').text(correction.article.name)

    if(correction.article.link) {
        let link = $("<a>", {
            class: "hover:underline",
            href: correction.article.link,
            target: "_blank",
            text: correction.article.name})
        template.find("#correction-name").append(link)
    } else {
        template.find("#correction-name").addClass("text-gray-500").text(correction.article.name)
    }

    template.find('#correction-words').text(correction.article.words)

    let authorLink = $("<a>", {
        class: "underline",
        href: `/user/${correction.author.id}`,
        text: correction.author.nickname})

    template.find('#correction-author').append(authorLink)
    template.find('#correction-timestamp').text(dateAsLocal(correction.timestamp))

    if(hasAuth) {
        let action_template = $("#correction-actions-template").contents().clone(true, true)
        action_template.find("#correction-delete").on("click", () => {deleteModalOpen(correction.article.id, correction.article.name, true)})
        template.append(action_template)
    }

    $('#co-articles').append(template)
}

async function fetchPage(page, sort = 'latest', type = 'translation') {
    const pageData = await fetch(`/api/user/${uid}/articles?` + new URLSearchParams({p: page, s: sort, t: type})).then(response => response.json())
    setPageCount(Math.ceil(pageData.total/15))
    return pageData
}

function searchArticle(query) {
    if (query == "" || query.length <= 2) {
        if(isSearching) {
            isSearching = false
            showPage(0)
        }
        return
    }
    isSearching = true
    $('.usr-row').animate({opacity: 0}, 300)
    fetch('/api/search/article?' + new URLSearchParams({
        'q': query,
        'u': uid
    })).then(response => response.json()).then(r => {
        currentData = r
        setPageCount(Math.ceil(r.result.length/15))
        showPage(0)
    })

}

async function setType(type) {
    setSelectedType(type)
    switch (type) {
        case 'translation':
            $("#search-field").on("input", handleSearch)
            currentType = type
            console.log("Set type to Translation")
            await showPage(0)
            $(".active-table").replaceWith($('#translation-table-partial').contents().clone(true, true).addClass('active-table'))
            setSelectedPage(0)
            setSorting('latest')
            break

        case 'correction':
            $("#search-field").off("input", handleSearch)
            currentType = type
            console.log("Set type to Correction")
            $(".active-table").replaceWith($('#correction-table-partial').contents().clone(true, true).addClass('active-table'))
            showPage(0)
            break

        case 'original':
            currentType = type
            console.log("Set type to Original")
            $("#search-field").off("input", handleSearch)
            $(".active-table").replaceWith($('#original-table-partial').contents().clone(true, true).addClass('active-table'))
            showPage(0)
            break

        default:
            console.error("Unknown type")
            break
    }
}

function handleSearch(e) {
    clearTimeout(timeoutID)
    if(e.target.value.length > 1) {
        timeoutID = setTimeout(searchArticle, 300, e.target.value)
    } else {
        searchArticle(e.target.value)
    }
}

$("#search-field").on("input", handleSearch)
setSelectedPage(0)
setSelectedSorter('latest')
setSelectedType('translation')

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
    console.log(`search for ${query}`)
    $('#result-table-body').empty()
    fetch('/api/search/article?' + new URLSearchParams({
        'q': query,
        'u': -1
    })).then(response => response.json()).then(r => r.result.slice(0, 10).forEach(result => addPickerItem(result)))
}

function handlePickerSearch(e) {
    clearTimeout(timeoutID)
    if(e.target.value.length > 2) {
        timeoutID = setTimeout(searchPickerArticle, 300, e.target.value)
    }
}

