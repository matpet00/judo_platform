import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { ChatParticipantKind } from "../api/types";

type Role = "trainer" | "parent";

function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

function formatTime(value: string): string {
  return new Date(value).toLocaleString("cs-CZ", {
    day: "numeric",
    month: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type ChatPageProps = {
  role: Role;
  selfId: number;
  homePath: string;
};

export function ChatPage({ role, selfId, homePath }: ChatPageProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<number | null>(null);
  const [showContacts, setShowContacts] = useState(false);
  const [draft, setDraft] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");
  const [contactSearch, setContactSearch] = useState("");

  const conversationsQuery = useQuery({
    queryKey: ["chat-conversations", role, selfId],
    queryFn: () => api.chatConversations(role),
    refetchInterval: 10000,
  });
  const conversations = conversationsQuery.data ?? [];
  const active = useMemo(() => conversations.find((c) => c.id === activeId) ?? null, [conversations, activeId]);

  const contactsQuery = useQuery({
    queryKey: ["chat-contacts", role, selfId],
    queryFn: () => api.chatContacts(role),
    enabled: showContacts,
  });

  const messagesQuery = useQuery({
    queryKey: ["chat-messages", activeId, role],
    queryFn: () => api.chatMessages(activeId as number, role),
    enabled: activeId !== null,
    refetchInterval: 5000,
  });
  const messages = messagesQuery.data ?? [];

  const invalidateConversations = () =>
    queryClient.invalidateQueries({ queryKey: ["chat-conversations", role, selfId] });

  const markRead = useMutation({
    mutationFn: (id: number) => api.markConversationRead(id, role),
    onSuccess: invalidateConversations,
  });

  const deleteConversation = useMutation({
    mutationFn: (id: number) => api.deleteConversation(id, role),
    onSuccess: (_data, id) => {
      if (activeId === id) setActiveId(null);
      invalidateConversations();
    },
  });

  const sendMessage = useMutation({
    mutationFn: (body: string) => api.sendChatMessage(activeId as number, body, role),
    onSuccess: () => {
      setDraft("");
      queryClient.invalidateQueries({ queryKey: ["chat-messages", activeId, role] });
      invalidateConversations();
    },
  });

  const invalidateMessages = () =>
    queryClient.invalidateQueries({ queryKey: ["chat-messages", activeId, role] });

  const editMessage = useMutation({
    mutationFn: ({ id, body }: { id: number; body: string }) =>
      api.editChatMessage(activeId as number, id, body, role),
    onSuccess: () => {
      setEditingId(null);
      setEditText("");
      invalidateMessages();
      invalidateConversations();
    },
  });

  const deleteMessage = useMutation({
    mutationFn: (id: number) => api.deleteChatMessage(activeId as number, id, role),
    onSuccess: () => {
      invalidateMessages();
      invalidateConversations();
    },
  });

  const startConversation = useMutation({
    mutationFn: ({ kind, id }: { kind: ChatParticipantKind; id: number }) =>
      api.startConversation(kind, id, role),
    onSuccess: (conversation) => {
      setShowContacts(false);
      setActiveId(conversation.id);
      invalidateConversations();
    },
  });

  const openConversation = (id: number, unread: number) => {
    setActiveId(id);
    if (unread > 0) markRead.mutate(id);
  };

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const stickToBottom = useRef(true);

  useEffect(() => {
    stickToBottom.current = true;
  }, [activeId]);

  useEffect(() => {
    if (stickToBottom.current) {
      bottomRef.current?.scrollIntoView({ block: "end" });
    }
  }, [messages.length, activeId]);

  // Contact picker view (typeahead)
  if (showContacts) {
    const contacts = contactsQuery.data ?? [];
    const query = normalize(contactSearch);
    const matches = query
      ? contacts.filter((c) => normalize(`${c.name} ${c.subtitle ?? ""}`).includes(query)).slice(0, 25)
      : [];
    const closeContacts = () => {
      setShowContacts(false);
      setContactSearch("");
    };
    return (
      <div className="boot-screen app-shell">
        <div className="chat-shell">
          <header className="chat-header">
            <button type="button" className="chat-header__back" onClick={closeContacts}>
              ← Zpět
            </button>
            <h1 className="chat-header__title">Nová konverzace</h1>
          </header>

          <input
            className="chat-contact-search"
            value={contactSearch}
            onChange={(e) => setContactSearch(e.target.value)}
            placeholder="Začni psát jméno…"
            autoFocus
          />

          {contactsQuery.isLoading && <div className="loading">Načítám kontakty…</div>}
          {!contactsQuery.isLoading && !query && (
            <div className="loading">Napiš jméno trenéra nebo rodiče.</div>
          )}
          <ul className="chat-contacts">
            {matches.map((contact) => (
              <li key={`${contact.kind}:${contact.id}`}>
                <button
                  type="button"
                  className="chat-contact"
                  disabled={startConversation.isPending}
                  onClick={() => {
                    setContactSearch("");
                    startConversation.mutate({ kind: contact.kind, id: contact.id });
                  }}
                >
                  <span className="chat-contact__name">{contact.name}</span>
                  <span className="chat-contact__sub">{contact.subtitle}</span>
                </button>
              </li>
            ))}
            {!contactsQuery.isLoading && query && matches.length === 0 && (
              <li className="loading">Nikdo neodpovídá „{contactSearch}".</li>
            )}
          </ul>
        </div>
      </div>
    );
  }

  // Active conversation view
  if (activeId !== null) {
    return (
      <div className="boot-screen app-shell">
        <div className="chat-shell">
          <header className="chat-header">
            <button type="button" className="chat-header__back" onClick={() => setActiveId(null)}>
              ← Zpět
            </button>
            <h1 className="chat-header__title">{active?.counterpart?.name ?? "Konverzace"}</h1>
          </header>

          <div
            className="chat-messages"
            ref={messagesRef}
            onScroll={() => {
              const el = messagesRef.current;
              if (!el) return;
              stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
            }}
          >
            {messagesQuery.isLoading && <div className="loading">Načítám…</div>}
            {messages.map((message) => {
              const mine = message.sender_kind === role && message.sender_id === selfId;
              const edited = message.updated_at !== message.created_at;
              return (
                <div key={message.id} className={`chat-bubble${mine ? " chat-bubble--mine" : ""}`}>
                  {editingId === message.id ? (
                    <div className="chat-bubble__edit">
                      <input value={editText} onChange={(e) => setEditText(e.target.value)} />
                      <div className="chat-bubble__edit-actions">
                        <button
                          type="button"
                          className="chat-bubble__action"
                          onClick={() => {
                            setEditingId(null);
                            setEditText("");
                          }}
                        >
                          Zrušit
                        </button>
                        <button
                          type="button"
                          className="chat-bubble__action"
                          disabled={!editText.trim() || editMessage.isPending}
                          onClick={() => editMessage.mutate({ id: message.id, body: editText.trim() })}
                        >
                          Uložit
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p className="chat-bubble__body">{message.body}</p>
                      <span className="chat-bubble__time">
                        {formatTime(message.created_at)}
                        {edited ? " · upraveno" : ""}
                      </span>
                      {mine && (
                        <div className="chat-bubble__actions">
                          <button
                            type="button"
                            className="chat-bubble__action"
                            onClick={() => {
                              setEditingId(message.id);
                              setEditText(message.body);
                            }}
                          >
                            Upravit
                          </button>
                          <button
                            type="button"
                            className="chat-bubble__action chat-bubble__action--danger"
                            disabled={deleteMessage.isPending}
                            onClick={() => deleteMessage.mutate(message.id)}
                          >
                            Smazat
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              );
            })}
            {!messagesQuery.isLoading && messages.length === 0 && (
              <div className="loading">Zatím žádné zprávy. Napiš první.</div>
            )}
            <div ref={bottomRef} />
          </div>

          <form
            className="chat-input"
            onSubmit={(e) => {
              e.preventDefault();
              if (draft.trim() && !sendMessage.isPending) sendMessage.mutate(draft.trim());
            }}
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Napiš zprávu…"
              disabled={sendMessage.isPending}
            />
            <button type="submit" className="btn btn--primary" disabled={!draft.trim() || sendMessage.isPending}>
              {sendMessage.isPending ? "…" : "Odeslat"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // Conversation list view
  return (
    <div className="boot-screen app-shell">
      <div className="chat-shell">
        <header className="chat-header">
          <button type="button" className="chat-header__back" onClick={() => navigate(homePath)}>
            ← Zpět
          </button>
          <h1 className="chat-header__title">Chat</h1>
          <button type="button" className="chat-header__new" onClick={() => setShowContacts(true)}>
            + Nová
          </button>
        </header>

        {conversationsQuery.isLoading && <div className="loading">Načítám…</div>}
        <ul className="chat-conversations">
          {conversations.map((conversation) => (
            <li key={conversation.id} className="chat-conversation-row">
              <button
                type="button"
                className="chat-conversation"
                onClick={() => openConversation(conversation.id, conversation.unread_count)}
              >
                <span className="chat-conversation__top">
                  <span className="chat-conversation__name">
                    {conversation.counterpart?.name ?? "Konverzace"}
                  </span>
                  {conversation.unread_count > 0 && (
                    <span className="chat-conversation__badge">{conversation.unread_count}</span>
                  )}
                </span>
                <span className="chat-conversation__preview">
                  {conversation.last_message ? conversation.last_message.body : "Zatím žádné zprávy"}
                </span>
              </button>
              <button
                type="button"
                className="chat-conversation__delete"
                aria-label="Smazat konverzaci"
                title="Smazat konverzaci (jen u mě)"
                disabled={deleteConversation.isPending}
                onClick={() => deleteConversation.mutate(conversation.id)}
              >
                ✕
              </button>
            </li>
          ))}
          {!conversationsQuery.isLoading && conversations.length === 0 && (
            <li className="loading">Zatím žádné konverzace. Založ novou tlačítkem „+ Nová".</li>
          )}
        </ul>
      </div>
    </div>
  );
}
