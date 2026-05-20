const linksWindowTemplate = $("#extra-link-win-tpl");
const openWindows = new Set()

async function openExtraLinks(event, article) {
    if(openWindows.has(article)) return;
    const windowID = `link-window-${article}`;
    const cloned = linksWindowTemplate.contents().clone(true, true);
    cloned.attr("id", windowID)
    cloned.find(".close-btn").on("click", ()=>{closeWindow(article)})
    fetch(`/api/article/${article}/links`).then((data) => data.json()).then(
        (data) => {
            cloned.find(".lt-window-title").text(`Odkazy pro ${data.title}`)
            cloned.find(".lt-tab-body").append(`<tr>
                    <td><a target="_blank" href="${data.mainLink}" class="underline hover:text-white/50 transition-all">${data.title}</a></td>
                    <td>N/A</td>
                </tr>`)
            
            data.result.forEach(link => {
            cloned.find(".lt-tab-body").append(`<tr>
                    <td><a href="${link.link}" target="_blank" class="underline hover:text-white/50 transition-all">${link.title}</a></td>
                    <td>${link.desc ?? "N/A"}</td>
                    <td><button class="tiny-btn">Odstranit</button>
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

function closeWindow(id) {
    openWindows.delete(id)
    $(`#link-window-${id}`).draggable("destroy").fadeOut(150, function(){$(this).remove()})
}