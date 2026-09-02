let j7
/** @type {Map<string, Wiki>} */
let wikis = new Map()

// ========== HELPERS ==========

const listDir = (path) => j7.FS.readdir(path).filter(e => {return e != '.' && e != '..'})

const make7ZRunner = async () => {
    // Create a new instance with sensible defaults for the output handlers
    let instance = await JS7z({
        print: msg => console.log('[7z] ' + msg),
        printErr: msg => console.log('[7z ERR] ' + msg)
    })

    // Create a global directory and mount the global filesystem into it
    instance.FS.mkdir('/global')
    instance.FS.mount(instance.PROXYFS, {root: '/', fs: j7.FS}, '/global')
    return instance
}

// ========== CONTAINER CLASSES ==========

class User {
    /** @type {string} */
    accountType
    /** @type {string} */
    fullName
    /** @type {string} */
    username
    /** @type {number} */
    createdTimestamp
    /** @type {number} */
    karma
    /** @type {number} */
    globalID
    constructor(json) {
        this.accountType = json.account_type
        this.fullName = json.full_name
        this.username = json.username
        this.karma = json.activity
        this.globalID = json.user_id
        this.createdTimestamp = json.wikidot_user_since
    }
}

class UserList {
    /** @type {Map<number, User>} */
    users

    constructor() {
        const usersPath = '/output/backup/_users'
        let userListFiles = listDir(usersPath)
        for(const user of userListFiles) {
            const currentUserPath = usersPath + '/' + user
            const data = j7.FS.readFile(currentUserPath, {encoding: 'utf8'})
            try {
                const userObj = new User(JSON.parse(data))
                this.users[userObj.globalID] = userObj
            } catch {
                console.error("Error parsing user meta: " + user)
                return
            }
        }
    }
}

class Revision {
    constructor(json) {
        this.localID = json.revision
        this.globalID = json.global_revision
        this.authorID = json.author
        this.timestamp = json.stamp
        this.flags = json.flags
        this.note = json.commentary
    }
}

class Page {
    /** @type {string} */
    slug
    /** @type {number} */
    version
    /** @type {number} */
    globalID
    /** @type {string} */
    parentPage
    /** @type {number} */
    rating
    /** @type {string} */
    title
    /** @type {string[]} */
    tags
    /** @type {Revision[]} */
    revisions

    constructor(path) {
        const data = j7.FS.readFile(path, {encoding: 'utf8'})
        let json
        try {
            json = JSON.parse(data)
        } catch {
            console.error("Error parsing page meta: " + path)
            return
        }
        this.slug = json.name
        this.version = json.version
        this.globalID = json.page_id
        this.parentPage = json.parent
        this.rating = json.rating
        this.title = json.title
        this.tags = json.tags
        this.revisions = json.revisions.map(r => new Revision(r))
    }
}

class WikiFile {
    /** @type {number} */
    globalID
    /** @type {string} */
    url
    /** @type {string} */
    path

    constructor(id, url, path) {
        this.globalID = id
        this.url = url
        this.path = decodeURIComponent(path)
    }

    getFilename() {
        return this.path.split('/').at(-1)
    }
}

class Wiki {
    /** @type {Map<number, Page>} */
    pages = new Map()

    /** @type {Map<number, WikiFile>} */
    files = new Map()

    /** @type {string} */
    name

    constructor(name) {
        this.name = name
        const metaDirPath = '/output/backup/'+name+'/meta/pages'
        const pageList = listDir(metaDirPath)
        pageList.forEach(page => {
            const pageObj = new Page(metaDirPath + '/' + page)
            this.pages.set(pageObj.globalID, pageObj)
        })

        const fileMap = j7.FS.readFile(`/output/backup/${name}/meta/file_map.json`, {encoding: 'utf8'})
        let fileMapObj
        try {
            fileMapObj = JSON.parse(fileMap)
        } catch {
            console.error("Error parsing file map")
            return
        }
        
        for(const [id, data] of Object.entries(fileMapObj)) {
            this.files.set(parseInt(id), new WikiFile(id, data.url, data.path))
        }
    }

    #createPagesNode() {
        let root = {
            id: 'pageroot;' + this.name,
            text: 'Stránky',
            children: []
        }
        this.pages.forEach((v, k, m) => {
            const id = 'page;' + this.name + ';' + k
            console.log("PROCESSED: ", id)
            let pageNode = {
                id: id,
                text: v.title,
                children: []
            }
            let revisionsNode = {
                id: id + ';revroot',
                text: 'Revize', 
                children: []
            }
            v.revisions.forEach(r => {
                revisionsNode.children.push({
                    id: id + ';' + r.globalID,
                    text: r.globalID
                })
            })
            pageNode.children.push({
                id: id+';info',
                text: 'Info',
                icon: "bi bi-info"
            })
            pageNode.children.push(revisionsNode)
            root.children.push(pageNode)
        })
        return root
    }

    #createForumsNode() {
        return {
            id: 'forumroot;' + this.name,
            text: 'Fóra'
        }
    }

    #createFilesNode() {
        let root = {
            id: 'fileroot;' + this.name,
            text: 'Soubory',
            children: []
        }
    }

    toTreeNode() {
        let root = {
            id: 'wikiroot;' + this.name,
            text: this.name,
            children: [
                this.#createPagesNode(),
                this.#createForumsNode(),
                this.#createFilesNode(),
            ]
        }
        return root
    }

    async extractPage(pageID) {
        if(!j7.FS.analyzePath('/cache/' + pageID).exists) {
            j7.FS.mkdir('/cache/' + pageID)
        } else {
            console.log("Cache hit on page ID " + pageID + ", skipping extraction")
            return
        }
        
        const extractor = await make7ZRunner()

        const pageArchiveName = this.pages.get(pageID).slug.replace(':', '_') + '.7z'
        const compressedPagePath = `/global/output/backup/${this.name}/pages/${pageArchiveName}`
        console.log("Will extract " + compressedPagePath)
        return new Promise((resolve, reject) => {
            extractor.onExit = (ec) => {
                if(ec === 0) {
                    resolve()
                } else {
                    console.log("Extraction failed")
                    reject()
                }
            }
            extractor.callMain(['x', compressedPagePath, '-oglobal/cache/' + pageID, '-y'])
        })
        
    }
}

// ========== NAV FUNCTIONS ==========

function loadMeta() {
    return listDir('/output/backup')
                    .filter(name => name != '_users')
                    .map(name => {wikis.set(name, new Wiki(name))})
}

function createExplorerTree() {
    let root = {
        id: 'wikiselect;',
        text: 'Wiki',
        state: {
            opened: false,
            selected: false,
            disabled: false,
        },
        children: []
    }
    wikis.forEach(w => {root.children.push(w.toTreeNode())})
    return root
}

function VFSFolderToJSON(path) {
    const data = []
    const entries = listDir(path)
    entries.forEach(e => {
        let jsonEntry = {};
        jsonEntry.text = decodeURIComponent(e);
        
        const entryPath = path+'/'+e
        const stat = j7.FS.stat(entryPath)
        if(j7.FS.isDir(stat.mode)) {
            jsonEntry.children = VFSFolderToJSON(entryPath)
        }
        data.push(jsonEntry)
    });
    return data;
}

function navInteractionHandler(event, data) {
    const selectPath = data.node.id.split(';')
    switch(selectPath[0]) {
        case 'page':
            const wiki = selectPath[1]
            const pageID = parseInt(selectPath[2])
            const pageRevision = selectPath[3]
            showPageInfo(wiki, pageID, pageRevision)
            break
        case 'wikiroot':
        case 'wikiselect':
        case 'pageroot':
        case 'forumroot':
        case 'fileroot':
        default:
            showNoData()
            break
    }
}

// ========== UI FUNCTIONS ==========

function switchScreen(screen) {
    if(screen == null) {
        // Hide all
        $('#loading-screen').hide(0).fadeOut(0)
        $('#page-info-screen').hide(0).fadeOut(0)
        $('#page-source-screen').hide(0).fadeOut(0)
        return
    }
    switch(screen) {
        case 'loading':
            switchScreen(null)
            $('#loading-screen').show().fadeIn(500)
            break
        case 'pageinfo':
            switchScreen(null)
            $('#page-info-screen').show().fadeIn(500)
            break
        case 'source':
            switchScreen(null)
            $('#page-source-screen').show().fadeIn(500)
            break

    }
}

async function showRevisionSource(wiki, pageID, revID) {
    $('#loading-title').text('Načítám revizi ' + pageID)
    $('#loading-status-text').text('Prosím čekejte')
    switchScreen('loading')

    const wikiObj = wikis.get(wiki)
    const revision = wikiObj.pages.get(pageID).revisions.find(r => r.globalID == revID)
    if(!revision) {
        console.error("couldn't find revision in page archive waawaaawaaa")
        return
    }
    await wikiObj.extractPage(pageID)
    const sourcePath = `/cache/${pageID}/${revision.localID}.txt`
    console.log("Reading source path: ", sourcePath)
    const data = j7.FS.readFile(sourcePath, {encoding: 'utf8'})
    $('#loading-title').text('OK')
    $('#loading-status-text').text('ok vro')
    console.log(data)
}

function showPageInfo(wiki, pageID, revID) {
    if(revID != null && !(isNaN(parseInt(revID)))) {
        showRevisionSource(wiki, pageID, revID).then(() => {return})
        return
    }    
    const page = wikis.get(wiki).pages.get(pageID)
    $('#pageinfo-title').text(page.title)
    $('#pageinfo-slug').text(page.slug)
    $('#pageinfo-version').text(page.version)
    $('#pageinfo-rating').text(page.rating)
    $('#pageinfo-globalid').text(page.globalID)
    $('#pageinfo-tags').empty()
    $('#pageinfo-tags').append(
        $('<p>', {
            'class': 'inline text-lg font-light',
            text: 'Štítky: '
        })
    )
    if(page.tags) {
        page.tags.forEach(tag => {
            $('#pageinfo-tags').append(
                $('<span>', {
                    'class': 'inline p-1 bg-white/5 border-white/20 text-sm border',
                    'text': tag
                })
            )
        })
    }
    switchScreen('pageinfo')
}

function showNoData() {
    console.log("Show N/A screen")
    $('#loading-title').text('Žádná data')
    $('#loading-status-text').text('Vyberte prosím jinou složku')
    switchScreen('loading')
}

// ========== LOADER ==========

function onDataLoaded() {
    loadMeta()
    $("#loading-status-text").text("Inicializuji UI");
    $("#nav-tree-container").jstree({'core': {
        'data': createExplorerTree()
    }});
    $('#nav-tree-container').on('changed.jstree', navInteractionHandler)
    $("#loading-status-text").text("Hotovo. Prosím vyberte složku");
}

$(async () => {
    switchScreen('source')
    return
    const params = new URLSearchParams(document.location.search)
    const id = params.get('backup_id')

    if(id == null) {
        $("#loading-title").text("Chyba")
        $("#loading-status-text").text("Je vyžadováno ID zálohy")
        return
    }

    $("#loading-screen").fadeIn({duration: 500})
    $("#loading-status-text").text("Stahuji archiv")

    fetch(`${document.location.origin}/backup/${id}/download`).then(
        async (response) => {
            $("#loading-status-text").text("Soubor stažen");
            return new Uint8Array(await response.arrayBuffer())
        }
    ).then(
        async (data) => {
            $("#loading-status-text").text("Inicializuji souborový systém");
            j7 = await JS7z({
                print: (text) => {
                console.log('[7z]' + text)
                $("#loading-status-text").text("Extrahuji archiv: " + text);
            }
            })
            
            j7.printErr = (text) => console.error('[7z ERR]', text)
            j7.onExit = onDataLoaded

            console.log('js7z initialized')

            $("#loading-status-text").text("Zapisuji soubory");
            j7.FS.mkdir('/input')
            j7.FS.writeFile('/input/bak.7z', data)
            j7.FS.mkdir('/cache')

            console.log('Write file to virtual FS')

            j7.FS.mkdir('/output')

            console.log('Call WASM 7z to decompress')
            await j7.callMain(['x', '/input/bak.7z', '-ooutput', '-y'])

        }
    )
})