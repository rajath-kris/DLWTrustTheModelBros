export interface MockInteraction {
  role: "ai" | "user";
  text: string;
  timestamp: string;
}

export const MOCK_INTERACTION_LOG: MockInteraction[] = [
  {
    role: "ai",
    text: "Looking at this diagram of an AVL tree rotation, what do you think happens to the balance factor of the parent after a left rotation?",
    timestamp: "2026-03-01T10:42:00Z",
  },
  {
    role: "user",
    text: "I think it's because the left subtree gets one level shorter?",
    timestamp: "2026-03-01T10:43:00Z",
  },
  {
    role: "ai",
    text: "Good direction. How does that relate to the invariants of a BST?",
    timestamp: "2026-03-01T10:44:00Z",
  },
  {
    role: "user",
    text: "The inorder sequence is preserved so the tree is still valid.",
    timestamp: "2026-03-01T10:45:00Z",
  },
];
