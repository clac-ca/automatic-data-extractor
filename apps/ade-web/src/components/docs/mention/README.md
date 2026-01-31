# Mention

Local wrapper: `src/components/ui/mention.tsx`

## Basic Usage

```tsx
import {
  Mention,
  MentionLabel,
  MentionInput,
  MentionContent,
  MentionItem,
} from "@/components/ui/mention";

const users = [
  { value: "ada", label: "Ada Lovelace" },
  { value: "grace", label: "Grace Hopper" },
  { value: "linus", label: "Linus Torvalds" },
];

return (
  <Mention>
    <MentionLabel>Assignee</MentionLabel>
    <MentionInput placeholder="Type @ to mention" />
    <MentionContent>
      {users.map((user) => (
        <MentionItem key={user.value} value={user.value} label={user.label}>
          {user.label}
        </MentionItem>
      ))}
    </MentionContent>
  </Mention>
);
```

## Custom Trigger

```tsx
<Mention trigger="#">
  <MentionLabel>Tags</MentionLabel>
  <MentionInput placeholder="Type # to tag" />
  <MentionContent>
    <MentionItem value="frontend">Frontend</MentionItem>
    <MentionItem value="backend">Backend</MentionItem>
  </MentionContent>
</Mention>
```

## Custom Filter

```tsx
<Mention
  onFilter={(options, term) =>
    options.filter((option) => option.toLowerCase().startsWith(term.toLowerCase()))
  }
>
  <MentionLabel>Team</MentionLabel>
  <MentionInput placeholder="Type @ to mention" />
  <MentionContent>
    <MentionItem value="alex">Alex</MentionItem>
    <MentionItem value="brian">Brian</MentionItem>
    <MentionItem value="casey">Casey</MentionItem>
  </MentionContent>
</Mention>
```

## Keyboard Interactions

| Keys | Description |
| --- | --- |
| Enter | When open, selects the highlighted mention option. |
| ArrowUp | When open, highlights the previous mention option. |
| ArrowDown | When open, highlights the next mention option. |
| Home | When open, highlights the first mention option. |
| End | When open, highlights the last mention option. |
| Escape | Closes the mention popover and returns focus to the input. |
