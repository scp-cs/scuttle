/** @type {import('tailwindcss').Config} */
module.exports = {
    content: ["../templates/embeds/**/*.j2", "../framework/config/roles.yaml"], // Add the role config file for the backgrounds
    corePlugins: {
        preflight: false, // Disable the preflight / reset so that we don't break WikiDot's (or other sites) CSS
    },
    plugins: [],
}