let theme = "default"
let type = "translator"

const previewFrame = $("#preview-iframe")
const themeSelect = $("#sel-theme")
const typeSelect = $("#sel-type")

const translatorThemes = JSON.parse(document.currentScript.getAttribute("data-tr-themes"))
const writerThemes = JSON.parse(document.currentScript.getAttribute("data-wr-themes"))
const userId = document.currentScript.getAttribute("data-uid")

function updatePreviewURL() {
    const params = new URLSearchParams()
    params.append("type", typeSelect.val())
    params.append("theme", themeSelect.val())
    const url = './embed?' + params.toString()
    previewFrame.attr("src", url)
}

function generateWikidotSource() {
    const text = `[[include :scp-cs:component:scuttle-embed
|user= ${userId}
|type= ${themeSelect.val()}
|theme= ${typeSelect.val()}
]]`
    $("#ta-wikidot-code").text(text)
}

function updateThemeList() {
    themeSelect.empty()
    switch(typeSelect.val()) {
        case "translator":
            translatorThemes.forEach((theme) => themeSelect.append($('<option>', {value: theme, text: theme})))
            break
        case "writer":
            writerThemes.forEach((theme) => themeSelect.append($('<option>', {value: theme, text: theme})))
            break
    }
}

$(function() {
    updateThemeList()
    themeSelect.on("change", () => {
        updatePreviewURL()
        generateWikidotSource()
    })
    typeSelect.on("change", () => {
        updateThemeList()
        updatePreviewURL()
        generateWikidotSource()})
    $("#btn-copy-code").on("click", function() {
        $(this).text("Zkopírováno!")
        setTimeout(() => {$("#btn-copy-code").text("Zkopírovat kód")}, 1000)
    })
    new ClipboardJS('.clip-copy')
    $('#sel-type option[value="translator"]').prop('selected', true)
    $('#sel-theme option[value="default"]').prop('selected', true)
    generateWikidotSource()
})