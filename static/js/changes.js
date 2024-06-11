const modWindow = document.getElementById('modal-window')
const modOverlay = document.getElementById('modal-overlay')

let currentCorrector;
let currentGuid;
let currentLink;
let currentTitle;

let timeoutID = 0;

function clickOut(e) {
    if(!modWindow.contains(e.target)) {
        modalClose()
    }
}

function modalClose() {
    $("#modal-overlay").fadeOut(200)
    $(window).off("click", clickOut)
    $('#input-search').off('input', handleSearch)
}

function modalOpen(guid, correctorId, link, title) {
    $("#modal-overlay").css("display", "flex").hide().fadeIn(200)
    setTimeout(() => $(window).on("click", clickOut), 100)
    $('#input-search').on('input', handleSearch).val("")
    currentCorrector = correctorId;
    currentGuid = guid;
    currentLink = link;
    currentTitle = title;
}

function addTranslationRow(row) {
    const template = $('#search-result-template')
    let newRow = template.contents().clone(true, true)
    newRow.find('#result-name').text(row.name)
    newRow.find('#result-author').text(row.author.name)
    newRow.find('#form-article').val(row.id)
    newRow.find('#form-corrector').val(currentCorrector)
    newRow.find('#form-guid').val(currentGuid)
    newRow.find('#form-link').val(currentLink)
    newRow.find('#form-title').val(currentTitle)
    $('#result-table-body').append(newRow)
}

function searchArticle(query) {
    console.log(`search for ${query}`)
    $('#result-table-body').empty()
    fetch('/api/search/article?' + new URLSearchParams({
        'q': query,
        'u': -1
    })).then(response => response.json()).then(r => r.result.slice(0, 10).forEach(result => addTranslationRow(result)))
}

function handleSearch(e) {
    clearTimeout(timeoutID)
    if(e.target.value.length > 2) {
        timeoutID = setTimeout(searchArticle, 300, e.target.value)
    }
}

