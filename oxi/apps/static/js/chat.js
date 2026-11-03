let user = null;
let form = null;
let msgcontainer = null;
let usercontainer = null;
let msgtxt = null;
let msgcolor = null;
let ws = null;
const msg_line = `<p class="red"><span style="color:{color};" id="username">{user}</span>:&nbsp;&nbsp;<span id="usermsg">{msg}</span></p>`

const sendmsg = ev => {
    ev.preventDefault();
    if (!user) doLogin();
    // console.log("Sending message...");
    if (msgtxt.value.length) {
        if (ws.readyState == ws.OPEN) {
            ws.send(JSON.stringify({type: 'chat.msg', user: user, message: msgtxt.value}));
            msgtxt.value = '';
        } else {
            alert("WebSocket closed.\nReloading chat room.");
            doLogin();
        }
    }
    return false;
}

const doLogin = () => {
    if (!user || user.length < 2)
        user = prompt("Please enter your username");
    if (!user) return;
    url = location.origin.replace('http', 'ws') + "/chat";
    console.log(`Connecting websocket to '${url}'`);
    ws = new WebSocket(url);
}

const updatelist = msg => {
    usercontainer.innerHTML = "";
    const users = msg.list;
    users.forEach(u => {
        p = document.createElement('p');
        p.textContent = u;
        if (u == user) {
            p.style.fontWeight = "bold";
            p.style.color = "steelblue";
        }
        usercontainer.appendChild(p);
    })
}

const onload = ev => {
    console.log("Page loaded.");

    msgcontainer = document.querySelector("#msgcontainer");
    usercontainer = document.querySelector("#usercontainer");
    msgtxt = document.querySelector("#msgtxt");
    form = document.querySelector("form");
    form.addEventListener("submit", sendmsg);
    msgcolor = document.querySelector("#msgcolor");
    msgcolor.addEventListener("change", ev => ws.send(JSON.stringify({type: 'register.color', color: ev.target.value})))
    
    doLogin();

    ws.onopen = _ => { 
        console.log("WebSocket connected to server.");
        ws.send(JSON.stringify({type: 'register.user', user: user}));
    }
    ws.onmessage = ev => {
        console.info(ev.data);
        console.log(typeof ev.data);
        msg = JSON.parse(ev.data);
        console.info(msg);
        if (msg.type == 'register.user' || msg.type == 'register.color') {
            console.log(`Trying to register color ${msg.color}`)
            msgcolor.value = msg.color ? msg.color : msgcolor.value;
            return;
        }
        if (msg.type == 'users.list') {
            return updatelist(msg);
        }

        if (msg.type != 'chat.msg') {
            return;
        }
        html = msg_line.replace('{color}', msg.color ? msg.color : 'green').replace('{user}', msg.user).replace('{msg}', msg.message);
        let p = document.createElement('p');
        p.innerHTML = html;
        msgcontainer.appendChild(p);
        msgcontainer.scrollTop = msgcontainer.scrollHeight;
    }

    ws.onerror = ev => {
        setTimeout(() => {
            alert("WebSocket error.\nReconnecting...");
            doLogin();
        }, 500);
    }
}

window.addEventListener("load", onload);

/*
window.addEventListener("unload", () => {
    ws.close();
    alert("WebSocket closed");
});
*/