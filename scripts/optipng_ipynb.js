const fs = require('fs')
const { execSync } = require('child_process')

function optipngBase64(base64) {
    const dir = fs.mkdtempSync('/tmp/optipng_ipynb')
    const fname = `${dir}/tmp.png`
    const input = Buffer.from(base64, 'base64')
    fs.writeFileSync(fname, input, { encoding: "base64" })
    execSync(`optipng '${fname}'`, {stdio: [0, 2, 2]})
    const output = fs.readFileSync(fname, { encoding: "base64" })
    return output
}

function optipngIpynb(obj) {
    if (!obj) return

    if (obj.data && obj.data['image/png']) {
        obj.data['image/png'] = optipngBase64(obj.data['image/png'])
    }

    if (Array.isArray(obj)) {
        obj.forEach(optipngIpynb)
    }
    else if (typeof obj === 'object') {
        for (let k in obj) {
            optipngIpynb(obj[k])
        }
    }
}

const input = fs.readFileSync("/dev/stdin", "utf8");
const parsed = JSON.parse(input)
optipngIpynb(parsed)
const output = JSON.stringify(parsed, null, 1)

console.log(output)
