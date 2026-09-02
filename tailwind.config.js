/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["templates/**/*.j2", "utils.py", "framework/accesscontrol.py", "static/js/*.js", "framework/config/roles.yaml"],
  safelist: ['animate-fadeout', 'animate-fadein', 'border-green-500', 'border-purple-600', 'border-yellow-400', 'border-red-600', 'border-rose-500', 'opacity-0'],
  theme: {
    extend: {
      animation: {
        timeout: 'timeout 5s linear',
        fadein: 'fadein 1s ease-in-out',
        fadeout: 'fadeout 1s ease-in-out'
      },
      keyframes: {
        timeout: {
          '0%': {width: '100%'},
          '100%': {width: '0%'}
        },
        fadein: {
          '0%': {opacity: '0', transform: 'translateY(10em)'},
          '40%': {opacity: '0'},
          '100%': {opacity: '1', transform: 'translateY(0)'}
        },
        fadeout: {
          '0%': {opacity: '1', transform: 'translateY(0)'},
          '100%': {opacity: '0', transform: 'translateY(10em)'}
        }
      }
    },
  },
  plugins: [],
}
