use std::{
    sync::{Mutex, mpsc::Sender},
    thread,
    time::{Duration, Instant},
};

use anyhow::{Result, anyhow};
use windows::Win32::{
    Foundation::{HINSTANCE, LPARAM, LRESULT, WPARAM},
    System::LibraryLoader::GetModuleHandleW,
    UI::{
        Input::KeyboardAndMouse::{
            VK_LCONTROL, VK_LMENU, VK_LSHIFT, VK_RCONTROL, VK_RMENU, VK_RSHIFT,
        },
        WindowsAndMessaging::{
            CallNextHookEx, DispatchMessageW, KBDLLHOOKSTRUCT, MSG, PM_REMOVE, PeekMessageW,
            SetWindowsHookExW, TranslateMessage, UnhookWindowsHookEx, WH_KEYBOARD_LL, WM_KEYDOWN,
            WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP,
        },
    },
};

use crate::triggers::BrokerKey;

static KEY_EVENT_SENDER: Mutex<Option<Sender<HookKeyEvent>>> = Mutex::new(None);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct HookKeyEvent {
    pub key: BrokerKey,
    pub pressed: bool,
}

#[allow(dead_code)]
pub fn run_keyboard_hook(sender: Sender<HookKeyEvent>) -> Result<()> {
    run_keyboard_hook_loop(sender, None)
}

pub fn run_keyboard_hook_for(sender: Sender<HookKeyEvent>, duration: Duration) -> Result<()> {
    run_keyboard_hook_loop(sender, Some(duration))
}

fn run_keyboard_hook_loop(sender: Sender<HookKeyEvent>, duration: Option<Duration>) -> Result<()> {
    {
        let mut current = KEY_EVENT_SENDER
            .lock()
            .map_err(|_| anyhow!("keyboard hook sender lock poisoned"))?;
        *current = Some(sender);
    }

    let module = unsafe { GetModuleHandleW(None)? };
    let hook = unsafe {
        SetWindowsHookExW(
            WH_KEYBOARD_LL,
            Some(low_level_keyboard_proc),
            Some(HINSTANCE(module.0)),
            0,
        )?
    };

    let started_at = Instant::now();
    let mut message = MSG::default();
    loop {
        while unsafe { PeekMessageW(&mut message, None, 0, 0, PM_REMOVE).as_bool() } {
            unsafe {
                let _ = TranslateMessage(&message);
                DispatchMessageW(&message);
            }
        }

        if duration.is_some_and(|limit| started_at.elapsed() >= limit) {
            break;
        }
        thread::sleep(Duration::from_millis(10));
    }

    unsafe {
        UnhookWindowsHookEx(hook)?;
    }
    let mut current = KEY_EVENT_SENDER
        .lock()
        .map_err(|_| anyhow!("keyboard hook sender lock poisoned"))?;
    *current = None;
    Ok(())
}

unsafe extern "system" fn low_level_keyboard_proc(
    code: i32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    if code >= 0 {
        let message = wparam.0 as u32;
        let pressed = message == WM_KEYDOWN || message == WM_SYSKEYDOWN;
        let released = message == WM_KEYUP || message == WM_SYSKEYUP;
        if pressed || released {
            let hook = unsafe { *(lparam.0 as *const KBDLLHOOKSTRUCT) };
            if let Some(key) = map_vk_to_key(hook.vkCode) {
                if let Ok(sender_guard) = KEY_EVENT_SENDER.lock() {
                    if let Some(sender) = sender_guard.as_ref() {
                        let _ = sender.send(HookKeyEvent { key, pressed });
                    }
                }
            }
        }
    }
    unsafe { CallNextHookEx(None, code, wparam, lparam) }
}

fn map_vk_to_key(vk_code: u32) -> Option<BrokerKey> {
    const VK_F23: u32 = 0x86;
    const VK_F24: u32 = 0x87;
    const VK_D: u32 = 0x44;
    const VK_F: u32 = 0x46;

    if vk_code == VK_F23 {
        return Some(BrokerKey::F23);
    }
    if vk_code == VK_F24 {
        return Some(BrokerKey::F24);
    }
    if vk_code == VK_LCONTROL.0 as u32 {
        return Some(BrokerKey::LeftCtrl);
    }
    if vk_code == VK_RCONTROL.0 as u32 {
        return Some(BrokerKey::RightCtrl);
    }
    if vk_code == VK_LSHIFT.0 as u32 {
        return Some(BrokerKey::LeftShift);
    }
    if vk_code == VK_RSHIFT.0 as u32 {
        return Some(BrokerKey::RightShift);
    }
    if vk_code == VK_LMENU.0 as u32 {
        return Some(BrokerKey::LeftAlt);
    }
    if vk_code == VK_RMENU.0 as u32 {
        return Some(BrokerKey::RightAlt);
    }
    if vk_code == VK_D {
        return Some(BrokerKey::D);
    }
    if vk_code == VK_F {
        return Some(BrokerKey::F);
    }
    if (0x30..=0x39).contains(&vk_code) || (0x41..=0x5A).contains(&vk_code) {
        return Some(BrokerKey::Other(vk_code as u16));
    }
    Some(BrokerKey::Other(vk_code as u16))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maps_f23_and_f24_virtual_keys() {
        assert_eq!(map_vk_to_key(0x86), Some(BrokerKey::F23));
        assert_eq!(map_vk_to_key(0x87), Some(BrokerKey::F24));
    }

    #[test]
    fn maps_left_and_right_control_virtual_keys() {
        assert_eq!(
            map_vk_to_key(VK_LCONTROL.0 as u32),
            Some(BrokerKey::LeftCtrl)
        );
        assert_eq!(map_vk_to_key(0xA3), Some(BrokerKey::RightCtrl));
    }
}
