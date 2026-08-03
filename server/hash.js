/**
 * Genera el hash bcrypt de una contrasena para meterlo en users.json.
 *   node hash.js miClaveSegura
 * Copia la linea que imprime a users.json:  "usuario": "<hash>"
 */
const bcrypt = require('bcryptjs')
const pw = process.argv[2]
if (!pw) {
  console.error('uso: node hash.js <contrasena>')
  process.exit(1)
}
console.log(bcrypt.hashSync(pw, 10))
