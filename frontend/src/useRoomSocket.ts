import { useEffect, useRef, useState } from 'react'
import type { ConnectionState, WsEvent } from './types'

export function useRoomSocket(
  roomId: string | null,
  onEvent: (event: WsEvent) => void,
  onOpen: () => void,
) {
  const [connection, setConnection] = useState<ConnectionState>('offline')
  const eventRef = useRef(onEvent)
  const openRef = useRef(onOpen)

  useEffect(() => {
    eventRef.current = onEvent
    openRef.current = onOpen
  }, [onEvent, onOpen])

  useEffect(() => {
    if (!roomId) {
      setConnection('offline')
      return
    }

    let stopped = false
    let socket: WebSocket | null = null
    let retry = 0
    let reconnectTimer: number | undefined
    let pingTimer: number | undefined
    let hasConnected = false

    const connect = () => {
      if (stopped) return
      setConnection(hasConnected ? 'reconnecting' : 'connecting')
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/rooms/${roomId}`)

      socket.onopen = () => {
        retry = 0
        hasConnected = true
        setConnection('live')
        openRef.current()
        pingTimer = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping' }))
          }
        }, 25_000)
      }

      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as WsEvent
          if (event.room_id === roomId) eventRef.current(event)
        } catch {
          // Ignore malformed frames.
        }
      }

      socket.onclose = (event) => {
        window.clearInterval(pingTimer)
        if (stopped) return
        if (event.code === 4404 || event.code === 4403 || retry >= 6) {
          setConnection('offline')
          return
        }
        setConnection('reconnecting')
        const delay = Math.min(8_000, 500 * 2 ** retry)
        retry += 1
        reconnectTimer = window.setTimeout(connect, delay)
      }

      socket.onerror = () => socket?.close()
    }

    connect()

    return () => {
      stopped = true
      window.clearTimeout(reconnectTimer)
      window.clearInterval(pingTimer)
      socket?.close()
      setConnection('offline')
    }
  }, [roomId])

  return connection
}
