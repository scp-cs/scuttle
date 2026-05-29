const linksWindowTemplate = $("#extra-link-win-tpl");
const openWindows = new Set()

let currentlyEditing = 0;

async function openExtraLinks(event, article) {
    if(openWindows.has(article)) return;
    let hasAuth = false;

    fetch('/api/nop').then(r => r.json()).then(r => {hasAuth = r.hasAuth})

    const windowID = `link-window-${article}`;
    const cloned = linksWindowTemplate.contents().clone(true, true);
    cloned.attr("id", windowID)
    cloned.find(".close-btn").on("click", ()=>{closeWindow(article)})
    // We have to do this because on() wouldn't capture the event (At least I think)
    cloned.find(".elw-editor-open").attr("onclick", `openLinkAddWindow(${article}, event)`)
    fetch(`/api/article/${article}/links`).then((data) => data.json()).then(
        (data) => {
            cloned.find(".lt-window-title").text(`Odkazy pro ${data.title}`)
            cloned.find(".lt-tab-body").append(`<tr>
                    <td><a target="_blank" href="${data.mainLink}" class="underline hover:text-white/50 transition-all">${data.title}</a></td>
                    <td>N/A</td>
                </tr>`)
            
            

            data.result.forEach((link, idx) => {
            const removeBtn = `<td><button class="tiny-btn" onclick="deleteLink('${link.link}', ${article}, ${idx})">Odstranit</button>`
            cloned.find(".lt-tab-body").append(`<tr id="link-row-${article}-${idx}">
                    <td><a href="${link.link}" target="_blank" class="underline hover:text-white/50 transition-all">${link.title}</a></td>
                    <td>${link.desc ?? "N/A"}</td>
                    ${hasAuth ? removeBtn : ""}
                </tr>`)
        });}
    )
    openWindows.add(article)
    $("body").append(cloned.hide().fadeIn(150))
    $(`#${windowID}`).draggable({handle: ".window-handle"}).css({
        position: "absolute",
        left: event.pageX+10,
        top: event.pageY+10
    })
}

function openLinkAddWindow(article, event) {
    currentlyEditing = article;
    $("#lt-add-window").find(".elw-window-title").text(`Přidat odkaz pro článek ${article}`)
    $("#lt-add-window").css({
        position: "absolute",
        left: event.pageX+10,
        top: event.pageY+10
    }).show()
}

function closeLinkAddWindow() {
    $("#lt-add-window").hide()
}

function addExtraLink() {
    const name = $("#elw-link-name").val()
    const url = $("#elw-link-url").val()
    const desc = $("#elw-link-desc").val() ?? null
    const endpoint = `/api/article/${currentlyEditing}/links/add`
    fetch(endpoint, {body: JSON.stringify({link: url, name: name, description: desc}), method: "POST"})
        .then(data => data.json())
        .then((json) => {
            if(json.status == "OK") {
                $("#elw-add-btn").addClass("border-green-500").delay(500).queue(function(n) {
                    $(this).removeClass("border-green-500")
                    n()
                })
            } else {
                $("#elw-add-btn").addClass("border-red-500").delay(500).queue(function(n) {
                    $(this).removeClass("border-red-500")
                    n()
                })
            }
        })
}

function closeWindow(id) {
    openWindows.delete(id)
    $(`#link-window-${id}`).draggable("destroy").fadeOut(150, function(){$(this).remove()})
}

function deleteLink(link, articleId, tabIndex) {
    fetch(`/api/article/${articleId}/links/remove`, {method: "POST", body: JSON.stringify({link: link})});
    $(`#link-window-${articleId} .lt-tab-body #link-row-${articleId}-${tabIndex}`).remove()
}

$("#lt-add-window").draggable({handle: ".window-handle"}).hide()