import { Component, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { failed: boolean };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  render(): ReactNode {
    if (this.state.failed) {
      return (
        <main role="alert">Не удалось показать страницу. Обновите её и попробуйте снова.</main>
      );
    }
    return this.props.children;
  }
}
