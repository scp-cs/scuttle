const table = document.getElementById('ut-body')
const originalTable = table.innerHTML

let isOriginal = true
let timeoutID = 0

function makeRow(user) {
    const discordBlock = user.discord ? `<img class="w-8 h-8 rounded-[50%] inline md:mr-4" src="/content/avatar/${user.discord}?s=thumb"> ${user.displayname ?? user.discord}` : user.displayname ?? user.discord
    return `<tr class="h-10 md:p-4 usr-row hover:bg-white/10 hover:border-white/20 hover:border transition-all rounded-md" id="u-${user.id}" onclick="window.location.href='/user/${user.id}'">
            <td data-label="Přezdívka">${user.nickname}</td>
            <td data-label="Discord ID">${discordBlock}</td>
            <td data-label="Počet překladů">${user.tr_count}</td>
            <td data-label="Počet korekcí">${user.cr_count}</td>
            <td data-label="Počet bodů">${user.points.toFixed(1)}</td>
            <td data-label="Role">${user.tr_role_html}</td>
        </tr>`
}

function search(query) {
    if (query == "" || query.length < 2) {
        $('#page-selector').removeClass('hidden')
        if(!isOriginal) {
            table.innerHTML = originalTable
            isOriginal = true
        }
        return
    }
    $("#page-selector").addClass('hidden')
    isOriginal = false
    let newHtml = ""
    fetch('/api/search/user?' + new URLSearchParams({
        'q': query
    }))
    .then(response => response.json())
    .then(r => r.result.forEach(user => {newHtml += makeRow(user)}))
    .then(() => table.innerHTML = newHtml)

}

function handleSearch(event) {
    clearTimeout(timeoutID)
    if(event.target.value.length > 1) {
        timeoutID = setTimeout(search, 300, event.target.value)
    } else {
        search(event.target.value)
    }
}

$("#search-field").on("input", handleSearch)